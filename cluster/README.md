# Training a CFR policy on MIT Engaging

The trainer is pure Python plus numpy. It parallelises across cores with
`multiprocessing`, so one node is usually the right unit of work: a 96-core
node does roughly 5,500 traversals a second, and the 12-hour limit on
`mit_normal` is about 2.4e8 traversals.

## One-time setup

```bash
bash cluster/sync.sh                                  # push backend/ + cluster/
ssh engaging 'bash ~/prdom/cluster/setup_env.sh'      # venv + numpy + pytest
```

`sync.sh` uses the `engaging` host from `~/.ssh/config`, which already keeps a
persistent ControlMaster, so neither command re-authenticates.

## Train

```bash
ssh engaging 'cd ~/prdom && sbatch cluster/cfr_train.sbatch tiny 200000 24'
```

Arguments are `LEVEL ITERS_PER_ROUND ROUNDS`. Output goes to
`/orcd/pool/007/$USER/prdom/<level>/`:

| file | what it is |
| --- | --- |
| `checkpoint.npz` | cumulative regret and strategy; resume from this |
| `policy.npz` | the exported strategy, what the bot loads |
| `meta.json` | traversals, level, wall time |

The job re-runs the CFR correctness gate (`tests/test_mccfr.py`,
`tests/test_cfr_engine.py`) on the node before training and refuses to start if
it fails. Rock-Paper-Scissors and Kuhn poker have known solutions; a CFR that
gets them wrong would otherwise burn the whole allocation and just look like a
mediocre bot at the end.

Re-submitting the same job resumes from `checkpoint.npz`, so a run longer than
12 hours is a matter of submitting again.

Watch it with:

```bash
ssh engaging 'squeue -u $USER; tail -f ~/prdom/prdom-cfr-*.out'
```

## Compare abstraction levels

The abstraction trades resolution against coverage, and which point on that
curve wins is an empirical question. `cfr_sweep.sbatch` trains all four levels
as one array job at equal compute and evaluates each:

```bash
ssh engaging 'cd ~/prdom && sbatch cluster/cfr_sweep.sbatch'
```

Results land in `/orcd/pool/007/$USER/prdom/sweep/<level>/eval.txt`.

## Bring the policy home

```bash
bash cluster/fetch.sh tiny        # -> backend/bots/cfr_policy.npz
python3 -m cfr.evaluate --policy backend/bots/cfr_policy.npz --matches 4000
```

`backend/bots/cfr_policy.npz` is where `CFRBot` looks by default, so once it is
in place the bot works in the arena and in the game with no further wiring.

## Scaling past one node

`cfr_train.sbatch` is single-node on purpose: everything stays in one process
tree and there is no barrier to go wrong. To use several nodes, pass `--task`
and `--ntasks` to `cfr.train` and it synchronises through a filesystem barrier
each round -- task 0 merges the shards, the rest wait for the merged
checkpoint. Launch it with `srun` rather than a job array so the tasks are
co-scheduled; an array whose tasks start hours apart will sit at the barrier
until it times out.

## Notes on the cluster

- `mit_normal` caps at 12 hours. `mit_general` is the account.
- Nodes are 96 cores / 377 GB, with a few at 192 cores / 1.5 TB.
- `OMP_NUM_THREADS=1` is set in the batch script: the trainer is
  process-parallel, and letting numpy also thread just oversubscribes.
- Home has a 200 GB quota, so run output goes to `/orcd/pool/007/$USER`.
