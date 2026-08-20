#!/bin/bash
#SBATCH --job-name=prdom-cfr
#SBATCH -p mit_normal
#SBATCH -t 12:00:00
#SBATCH -N 1
#SBATCH -c 96
#SBATCH --mem=240G
#SBATCH -o %x-%j.out
# Train one CFR policy on a single node. This is the recommended shape: no
# cross-node barrier, everything stays in one process tree.
#
#   sbatch cluster/cfr_train.sbatch [LEVEL] [ITERS_PER_ROUND] [ROUNDS]
#
# Defaults train the `tiny` abstraction. Output lands in
# /orcd/pool/007/$USER/prdom/<level>/ as checkpoint.npz plus policy.npz.
set -uo pipefail

LEVEL="${1:-tiny}"
ITERS="${2:-200000}"
ROUNDS="${3:-24}"

ROOT="$HOME/prdom"
POOL="/orcd/pool/007/$USER/prdom"
OUT="$POOL/$LEVEL"

export PATH="$ROOT/venv/bin:$PATH"
export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"
export PYTHONNOUSERSITE=True
export OMP_NUM_THREADS=1          # the trainer is process-parallel, not BLAS-bound
cd "$ROOT/backend"

WORKERS="${SLURM_CPUS_PER_TASK:-8}"
mkdir -p "$OUT"
echo "=== level=$LEVEL iters/round=$ITERS rounds=$ROUNDS workers=$WORKERS node=$(hostname) ==="

# The correctness gate: CFR is validated against Rock-Paper-Scissors and Kuhn
# poker before any of the 12-hour allocation is spent on it.
python3 -m pytest tests/test_mccfr.py tests/test_cfr_engine.py -q || {
  echo "FAILED the CFR correctness gate -- not training"; exit 2; }

RESUME=""
[ -f "$OUT/checkpoint.npz" ] && RESUME="--resume $OUT/checkpoint.npz"

python3 -m cfr.train \
  --out "$OUT" --level "$LEVEL" \
  --iters "$ITERS" --rounds "$ROUNDS" --workers "$WORKERS" \
  --seed "${SLURM_JOB_ID:-0}" $RESUME || exit 1

ls -lh "$OUT"
echo "=== TRAIN_DONE $LEVEL ==="
