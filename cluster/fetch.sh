#!/bin/bash
# Pull a trained policy back from Engaging into the repo.
# Usage: bash cluster/fetch.sh [LEVEL]   (default: tiny)
set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${PRDOM_REMOTE:-engaging}"
LEVEL="${1:-tiny}"
USER_REMOTE=$(ssh "$REMOTE" 'echo $USER')
SRC="/orcd/pool/007/$USER_REMOTE/prdom/$LEVEL/policy.npz"

ssh "$REMOTE" "ls -lh $SRC"
rsync -az --progress "$REMOTE:$SRC" backend/bots/cfr_policy.npz
ls -lh backend/bots/cfr_policy.npz
echo "installed as backend/bots/cfr_policy.npz"
