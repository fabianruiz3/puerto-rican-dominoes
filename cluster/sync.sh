#!/bin/bash
# Push the trainer to Engaging over the existing ssh ControlMaster.
# Usage: bash cluster/sync.sh
set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${PRDOM_REMOTE:-engaging}"
ROOT="${PRDOM_ROOT:-prdom}"

ssh "$REMOTE" "mkdir -p ~/$ROOT"
rsync -az --delete \
  --exclude '__pycache__' --exclude '.DS_Store' --exclude '*.pyc' \
  --exclude 'runs/' --exclude '.pytest_cache' \
  backend/ "$REMOTE:$ROOT/backend/"
rsync -az --exclude '.DS_Store' cluster/ "$REMOTE:$ROOT/cluster/"
echo "synced to $REMOTE:~/$ROOT"
ssh "$REMOTE" "ls -la ~/$ROOT"
