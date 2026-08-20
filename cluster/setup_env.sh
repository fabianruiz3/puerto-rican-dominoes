#!/bin/bash
# One-time environment setup on Engaging. Idempotent -- re-running repairs.
# Usage: ssh engaging 'bash ~/prdom/cluster/setup_env.sh'
set -uo pipefail

ROOT="${PRDOM_ROOT:-$HOME/prdom}"
LOG="$ROOT/setup_env.log"
exec > >(tee -a "$LOG") 2>&1
echo "=== setup_env start $(date) on $(hostname) ==="

module purge 2>/dev/null || true
for m in miniforge anaconda3 python/3.11 python/3.10 python; do
  if module load "$m" 2>/dev/null; then echo "loaded module: $m"; break; fi
done
PY=$(command -v python3)
echo "python: $PY -> $($PY --version 2>&1)"

if [ ! -x "$ROOT/venv/bin/python3" ]; then
  "$PY" -m venv "$ROOT/venv" || "$PY" -m venv --system-site-packages "$ROOT/venv"
fi
VPY="$ROOT/venv/bin/python3"
"$VPY" -m pip install --upgrade pip -q
# numpy is the only training dependency; pytest so the gate can run on-node.
"$VPY" -m pip install -q numpy pytest

"$VPY" - <<'PYEOF'
import numpy, sys
print("VERIFY numpy", numpy.__version__, "python", sys.version.split()[0])
PYEOF
echo "=== SETUP_DONE $(date) ==="
