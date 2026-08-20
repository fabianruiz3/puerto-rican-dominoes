"""Re-export a policy from a training checkpoint, at a chosen pruning level.

Training keeps every information set it ever touched, which at the richer
abstraction levels runs to hundreds of megabytes -- more than belongs in a
repository, and most of it is information sets visited a handful of times whose
averaged strategy is still close to noise. CFRBot falls back to the heuristic
on a lookup miss, so dropping those costs less than storing them.

    python3 -m cfr.export --checkpoint runs/coarse/checkpoint.npz --scan
    python3 -m cfr.export --checkpoint runs/coarse/checkpoint.npz \
        --min-mass 200 --out bots/cfr_policy.npz

`--scan` prints what each threshold would cost and keep, so the trade-off is
picked from numbers rather than guessed at.
"""

import argparse
import json
import os
import sys
import tempfile

import numpy as np

from .policy import from_arrays
from .train import load_checkpoint


def infoset_mass(info, strategy):
    """Total averaging weight per information set, and the set of keys."""
    order = np.argsort(info, kind="stable")
    info_sorted = info[order]
    strategy_sorted = strategy[order]
    keys, starts = np.unique(info_sorted, return_index=True)
    return keys, np.add.reduceat(strategy_sorted, starts)


def scan(info, action, strategy, level, meta):
    totals = infoset_mass(info, strategy)[1]
    live = totals[totals > 0]
    print(f"information sets with any weight: {live.size:,}")
    print(f"total averaging weight:           {live.sum():,.0f}")
    print()
    print(f"{'min-mass':>10} {'infosets kept':>15} {'share':>8} {'approx size':>12}")
    print("-" * 50)
    quantiles = [0.0] + [float(np.quantile(live, q)) for q in (0.25, 0.5, 0.75, 0.9, 0.95, 0.99)]
    for threshold in quantiles:
        kept = int((live > threshold).sum())
        if kept == 0:
            continue
        policy = from_arrays(info, action, strategy, level, threshold, meta)
        with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as fh:
            path = fh.name
        try:
            policy.save(path)
            size = os.path.getsize(path)
        finally:
            os.unlink(path)
        print(
            f"{threshold:>10.1f} {kept:>15,} {kept / live.size:>7.1%} "
            f"{size / 1e6:>11.1f}MB"
        )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--level", help="defaults to the level recorded alongside it")
    p.add_argument("--min-mass", type=float, default=0.0)
    p.add_argument("--out")
    p.add_argument("--scan", action="store_true", help="print the trade-off and stop")
    args = p.parse_args(argv)

    info, action, _regret, strategy = load_checkpoint(args.checkpoint)

    level = args.level
    meta = {}
    meta_path = os.path.join(os.path.dirname(args.checkpoint), "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as fh:
            meta = json.load(fh)
        level = level or meta.get("level")
    if level is None:
        p.error("--level is required when meta.json is not next to the checkpoint")

    if args.scan:
        scan(info, action, strategy, level, meta)
        return 0
    if not args.out:
        p.error("--out is required unless --scan is given")

    meta = {**meta, "min_mass": args.min_mass}
    policy = from_arrays(info, action, strategy, level, args.min_mass, meta)
    policy.save(args.out)
    print(
        f"wrote {args.out}: {policy.n_infosets:,} infosets, {len(policy):,} entries, "
        f"{os.path.getsize(args.out) / 1e6:.1f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
