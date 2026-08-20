#!/bin/bash
# Pull a trained policy back from Engaging and install it for CFRBot.
#
#   bash cluster/fetch.sh                 # the tiny policy from a plain run
#   bash cluster/fetch.sh compact         # a named level
#   bash cluster/fetch.sh sweep/compact   # a level from the sweep
#
# Looks in the plain run directory first, then under sweep/.
set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${PRDOM_REMOTE:-engaging}"
LEVEL="${1:-tiny}"
BASE="/orcd/pool/007/$(ssh "$REMOTE" 'echo $USER')/prdom"

SRC=""
for candidate in "$BASE/$LEVEL/policy.npz" "$BASE/sweep/$LEVEL/policy.npz"; do
  if ssh "$REMOTE" "test -f '$candidate'"; then SRC="$candidate"; break; fi
done
if [ -z "$SRC" ]; then
  echo "no policy.npz for '$LEVEL' under $BASE" >&2
  ssh "$REMOTE" "find '$BASE' -name policy.npz -printf '  %p  (%s bytes)\n' 2>/dev/null" >&2 || true
  exit 1
fi

echo "fetching $SRC"
rsync -az --progress "$REMOTE:$SRC" backend/bots/cfr_policy.npz
ls -lh backend/bots/cfr_policy.npz
echo
echo "installed. verify with:"
echo "  python3 -m cfr.evaluate --policy bots/cfr_policy.npz --matches 2000   # from backend/"
