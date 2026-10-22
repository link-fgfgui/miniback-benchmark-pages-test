#!/usr/bin/env bash
# Shortcut for the bundled 19-snapshot dataset.
# Requires work/worlds and datasets/legacy-19.tsv (see README).
set -euo pipefail
cd "$(dirname "$0")"

MANIFEST="${MANIFEST:-datasets/legacy-19.tsv}"
if [ ! -f "$MANIFEST" ]; then
    echo "missing $MANIFEST; build it with the snippet in README.md (Bundled dataset)" >&2
    exit 1
fi

exec python3 bench.py run --manifest "$MANIFEST" \
    --name "${NAME:-legacy-19}" \
    --levels "${LEVELS:-3,9}" \
    --long "${LONG:-off,on}" \
    --heap "${HEAP:-12g}" "$@"
