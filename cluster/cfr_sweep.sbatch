#!/bin/bash
#SBATCH --job-name=prdom-sweep
#SBATCH -p mit_normal
#SBATCH -t 12:00:00
#SBATCH -N 1
#SBATCH -c 96
#SBATCH --mem=240G
#SBATCH --array=0-3
#SBATCH -o %x-%A_%a.out
# One abstraction level per array task, so the levels can be compared at equal
# compute instead of guessed at. Read the win rates out of cfr_eval afterwards.
#
#   sbatch cluster/cfr_sweep.sbatch
set -uo pipefail

LEVELS=(tiny compact coarse standard)
LEVEL="${LEVELS[$SLURM_ARRAY_TASK_ID]}"

ROOT="$HOME/prdom"
OUT="/orcd/pool/007/$USER/prdom/sweep/$LEVEL"
export PATH="$ROOT/venv/bin:$PATH"
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
export PYTHONNOUSERSITE=True
export OMP_NUM_THREADS=1
cd "$ROOT/backend"
mkdir -p "$OUT"

WORKERS="${SLURM_CPUS_PER_TASK:-8}"
echo "=== sweep level=$LEVEL workers=$WORKERS node=$(hostname) ==="
python3 -m cfr.train --out "$OUT" --level "$LEVEL" \
  --iters 150000 --rounds 16 --workers "$WORKERS" --seed 7 || exit 1

python3 -m cfr.evaluate --policy "$OUT/policy.npz" --matches 3000 --seed 11 \
  | tee "$OUT/eval.txt"
echo "=== SWEEP_DONE $LEVEL ==="
