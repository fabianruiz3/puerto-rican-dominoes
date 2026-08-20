#!/bin/bash
#SBATCH --job-name=prdom-sweep
#SBATCH -p mit_normal
#SBATCH -t 02:00:00
#SBATCH -N 1
#SBATCH -c 32
#SBATCH --mem=64G
#SBATCH --array=0-2
#SBATCH -o %x-%A_%a.out
# One abstraction level per array task, at equal compute, so the levels are
# ranked by measured win rate instead of guessed at.
#
#   sbatch cluster/cfr_sweep.sbatch
#
# Sized to backfill rather than to be big. mit_normal routinely has ~700 jobs
# queued, and a whole 96-core node was quoted a two-day start; 32 cores for two
# hours slots into a partially-used node almost immediately. The sweep only has
# to rank the levels -- train the winner properly with cfr_train.sbatch.
#
# `standard` is not in the sweep because its table grows fast enough to be a
# memory risk at this iteration count -- extrapolating its observed growth puts
# it near 1e8 information sets. Given that coarse beat both smaller levels,
# standard is the one worth trying next; give it its own run with
# cfr_train.sbatch and a large --mem rather than adding it here.
set -uo pipefail

LEVELS=(tiny compact coarse)
LEVEL="${LEVELS[$SLURM_ARRAY_TASK_ID]}"
ITERS="${1:-60000}"
ROUNDS="${2:-20}"

ROOT="$HOME/prdom"
OUT="/orcd/pool/007/$USER/prdom/sweep/$LEVEL"
export PATH="$ROOT/venv/bin:$PATH"
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
export PYTHONNOUSERSITE=True
export OMP_NUM_THREADS=1
cd "$ROOT/backend"
mkdir -p "$OUT"

WORKERS="${SLURM_CPUS_PER_TASK:-8}"
echo "=== sweep level=$LEVEL iters=$ITERS rounds=$ROUNDS workers=$WORKERS node=$(hostname) ==="

python3 -m pytest tests/test_mccfr.py tests/test_cfr_engine.py -q || {
  echo "FAILED the CFR correctness gate -- not training"; exit 2; }

python3 -m cfr.train --out "$OUT" --level "$LEVEL" \
  --iters "$ITERS" --rounds "$ROUNDS" --workers "$WORKERS" --seed 7 || exit 1

python3 -m cfr.evaluate --policy "$OUT/policy.npz" --matches 3000 --seed 11 \
  | tee "$OUT/eval.txt"
echo "=== SWEEP_DONE $LEVEL ==="
