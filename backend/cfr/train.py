"""Train a dominoes policy with external-sampling MCCFR.

Runs in three shapes from the same code:

    local     one machine, a multiprocessing pool, rounds in memory
    task      one SLURM array task: same pool, shards to disk, waits at a
              filesystem barrier while task 0 merges the round
    merge     fold shards into a checkpoint and export a policy

Rounds exist so parallel workers can share what they have learned. Regret and
strategy sums are accumulations over iterations, so summing the deltas that
independent workers produced is the standard way to spread CFR across cores and
machines. Within a round a worker reads regret from the previous round's
checkpoint and writes only its own delta.
"""

import argparse
import json
import os
import random
import sys
import time
from multiprocessing import get_context

import numpy as np

from .abstraction import COARSE, LEVELS, actions_for, key_for, slot_key, slot_keys
from .engine import new_hand
from .mccfr import BaseTable, GameSpec, RegretTable, traverse
from .policy import from_arrays, merge_shards, save_shard, sum_by_pair

# Roughly one hand in eight opens a match, so that is how often the traversal
# should see the forced 6-6 lead. Later hands are opened by the previous
# winner, which correlates with how the hand went; the starter is sampled
# uniformly here instead, which is the one place the root distribution departs
# from match play.
DEFAULT_OPEN_PROB = 0.125


def make_spec(level: str, capicu: int = 100, chuchazo: int = 100) -> GameSpec:
    return GameSpec(
        actions=lambda sim, seat: actions_for(sim, seat, level),
        key=lambda sim, seat: key_for(sim, seat, level),
        utility=lambda sim, seat: sim.utility(seat & 1, capicu, chuchazo),
    )


def sample_root(rng, open_prob: float):
    if rng.random() < open_prob:
        return new_hand(rng, forced_open=True)
    return new_hand(rng, starter=rng.randrange(4), forced_open=False)


def run_iterations(
    iterations: int,
    table: RegretTable,
    rng,
    spec: GameSpec,
    weight: float = 1.0,
    open_prob: float = DEFAULT_OPEN_PROB,
    clamp_regret: bool = True,
) -> int:
    """Run `iterations` deals, traversing once per seat. Returns traversals."""
    for _ in range(iterations):
        sim = sample_root(rng, open_prob)
        # traverse() unwinds every mutation, so all four seats reuse one deal.
        for traverser in range(4):
            traverse(
                sim, traverser, table, rng, spec, slot_key, weight, clamp_regret
            )
    return iterations * 4


# ------------------------------------------------------------------- workers

_BASE = BaseTable()


def _init_worker(slots, regret):
    global _BASE
    _BASE = BaseTable(slots, regret)


def _work(args):
    seed, iterations, level, weight, open_prob, clamp = args
    table = RegretTable(base=_BASE)
    rng = random.Random(seed)
    spec = make_spec(level)
    started = time.time()
    traversals = run_iterations(
        iterations, table, rng, spec, weight, open_prob, clamp
    )
    info, action, regret, strategy = table.deltas()
    return (
        info,
        action,
        regret.astype(np.float32),
        strategy.astype(np.float32),
        traversals,
        time.time() - started,
    )


def run_round(
    pool,
    workers: int,
    iterations: int,
    level: str,
    weight: float,
    seed: int,
    open_prob: float,
    clamp: bool,
    task: int = 0,
):
    """One round across `workers` processes. Returns merged delta arrays.

    `task` separates SLURM array tasks. Without it every task seeds identically
    and samples the same deals in the same order, so N nodes cost N times the
    allocation and cover nothing extra.
    """
    per_worker = max(1, iterations // workers)
    jobs = [
        (
            (seed * 1_000_003 + task * 7_919 + w) & 0x7FFFFFFF,
            per_worker,
            level,
            weight,
            open_prob,
            clamp,
        )
        for w in range(workers)
    ]
    results = pool.map(_work, jobs) if pool is not None else [_work(j) for j in jobs]

    merged = sum_by_pair(
        np.concatenate([r[0] for r in results]),
        np.concatenate([r[1] for r in results]),
        np.concatenate([r[2] for r in results]).astype(np.float64),
        np.concatenate([r[3] for r in results]).astype(np.float64),
    )
    return merged + (sum(r[4] for r in results),)


# --------------------------------------------------------------- checkpoints


def accumulate(checkpoint, delta):
    """Add a round's delta onto the running checkpoint."""
    if checkpoint is None:
        return sum_by_pair(*delta[:4])
    return sum_by_pair(
        np.concatenate([checkpoint[0], delta[0]]),
        np.concatenate([checkpoint[1], delta[1]]),
        np.concatenate([checkpoint[2], delta[2]]),
        np.concatenate([checkpoint[3], delta[3]]),
    )


def base_from_checkpoint(checkpoint) -> tuple:
    """Sorted (slot, regret) arrays for the forked workers to read."""
    if checkpoint is None:
        return None, None
    info, action, regret, _ = checkpoint
    slots = slot_keys(info, action)
    order = np.argsort(slots)
    return np.ascontiguousarray(slots[order]), np.ascontiguousarray(regret[order])


def save_checkpoint(path: str, checkpoint) -> None:
    save_shard(path, *checkpoint)


def _rounds_recorded(checkpoint_path: str) -> int:
    """Rounds already completed, from the meta written beside the checkpoint.

    Linear averaging weights rounds by their index, so a resumed run has to
    carry on counting; restarting at 1 would give the later, better-informed
    rounds the same say as the first ones.
    """
    meta_path = os.path.join(os.path.dirname(checkpoint_path), "meta.json")
    try:
        with open(meta_path) as fh:
            return int(json.load(fh).get("rounds_total", 0))
    except (OSError, ValueError, TypeError):
        return 0


def load_checkpoint(path: str):
    with np.load(path, allow_pickle=False) as data:
        return (
            data["info"],
            data["action"],
            data["regret"].astype(np.float64),
            data["strategy"].astype(np.float64),
        )


# ------------------------------------------------------------ barrier (SLURM)


def _wait_for(paths, timeout: float, poll: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(os.path.exists(p) for p in paths):
            return
        time.sleep(poll)
    missing = [p for p in paths if not os.path.exists(p)]
    raise TimeoutError(f"barrier timed out waiting for {len(missing)} file(s): {missing[:3]}")


# ------------------------------------------------------------------ training


def train(args) -> None:
    os.makedirs(args.out, exist_ok=True)
    ctx = get_context("fork") if args.workers > 1 else None
    checkpoint = None
    rounds_done = 0
    if args.resume and os.path.exists(args.resume):
        checkpoint = load_checkpoint(args.resume)
        rounds_done = _rounds_recorded(args.resume)
        print(
            f"resumed {len(checkpoint[0]):,} slots from {args.resume} "
            f"({rounds_done} rounds already done)",
            flush=True,
        )

    total_traversals = 0
    started = time.time()
    for rnd in range(args.rounds):
        slots, regret = base_from_checkpoint(checkpoint)
        pool = None
        if ctx is not None:
            pool = ctx.Pool(
                args.workers, initializer=_init_worker, initargs=(slots, regret)
            )
        else:
            _init_worker(slots, regret)
        try:
            delta = run_round(
                pool,
                args.workers,
                args.iters,
                args.level,
                # Linear averaging: later rounds count more. Continues across a
                # resume so resubmitting does not reset the weighting to 1.
                weight=float(rounds_done + rnd + 1),
                seed=args.seed + rounds_done + rnd,
                open_prob=args.open_prob,
                clamp=not args.no_clamp,
                task=args.task or 0,
            )
        finally:
            if pool is not None:
                pool.close()
                pool.join()

        total_traversals += delta[4]
        if args.task is None:
            checkpoint = accumulate(checkpoint, delta)
        else:
            checkpoint = _sync_round(args, rnd, delta, checkpoint)

        elapsed = time.time() - started
        infosets = len(np.unique(checkpoint[0]))
        print(
            f"round {rnd + 1}/{args.rounds}  traversals {total_traversals:,}  "
            f"slots {len(checkpoint[0]):,}  infosets {infosets:,}  "
            f"{total_traversals / elapsed:,.0f} trav/s  {elapsed / 60:.1f} min",
            flush=True,
        )
        if args.task in (None, 0):
            save_checkpoint(os.path.join(args.out, "checkpoint.npz"), checkpoint)

    if args.task in (None, 0):
        args._rounds_total = rounds_done + args.rounds
        export(args, checkpoint, total_traversals, time.time() - started)


def _sync_round(args, rnd, delta, checkpoint):
    """Filesystem barrier across SLURM array tasks."""
    shard_dir = os.path.join(args.out, f"round{rnd}")
    os.makedirs(shard_dir, exist_ok=True)
    shard = os.path.join(shard_dir, f"shard{args.task}.npz")
    save_shard(shard, delta[0], delta[1], delta[2], delta[3])
    open(shard + ".done", "w").close()

    merged = os.path.join(args.out, f"run{_run_token(args)}", f"base{rnd}.npz")
    if args.task == 0:
        _wait_for(
            [
                os.path.join(shard_dir, f"shard{t}.npz.done")
                for t in range(args.ntasks)
            ],
            timeout=args.barrier_timeout,
        )
        shards = [
            os.path.join(shard_dir, f"shard{t}.npz") for t in range(args.ntasks)
        ]
        summed = merge_shards(shards)
        checkpoint = accumulate(checkpoint, summed + (0,))
        save_checkpoint(merged, checkpoint)
        open(merged + ".done", "w").close()
    else:
        _wait_for([merged + ".done"], timeout=args.barrier_timeout)
        checkpoint = load_checkpoint(merged)
    return checkpoint


def export(args, checkpoint, traversals, elapsed) -> None:
    meta = {
        "traversals": int(traversals),
        "level": args.level,
        "rounds": args.rounds,
        "rounds_total": int(getattr(args, "_rounds_total", args.rounds)),
        "open_prob": args.open_prob,
        "elapsed_seconds": round(elapsed, 1),
        "min_mass": args.min_mass,
    }
    policy = from_arrays(
        checkpoint[0], checkpoint[1], checkpoint[3], args.level, args.min_mass, meta
    )
    path = os.path.join(args.out, "policy.npz")
    policy.save(path)
    print(
        f"\nwrote {path}: {policy.n_infosets:,} infosets, {len(policy):,} entries, "
        f"{os.path.getsize(path) / 1e6:.1f} MB",
        flush=True,
    )
    with open(os.path.join(args.out, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--iters", type=int, default=20000, help="deals per round (all tasks)")
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--level", choices=list(LEVELS), default=COARSE)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--open-prob", type=float, default=DEFAULT_OPEN_PROB)
    p.add_argument("--min-mass", type=float, default=0.0)
    p.add_argument("--no-clamp", action="store_true", help="plain CFR, not CFR+")
    p.add_argument("--resume", help="checkpoint.npz to continue from")
    p.add_argument("--task", type=int, help="SLURM array task id (enables the barrier)")
    p.add_argument("--ntasks", type=int, default=1)
    p.add_argument("--barrier-timeout", type=float, default=3600.0)
    p.add_argument(
        "--run-id",
        help="namespaces the multi-node barrier; defaults to the SLURM job id",
    )
    args = p.parse_args(argv)
    train(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
