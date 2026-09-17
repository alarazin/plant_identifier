#!/bin/bash
# Allow incoming LAN connections to Node (Metro) and Python (the backend).
#
# Allow the local development servers through the macOS firewall.
# The firewall stays enabled.
#
# Usage:  bash scripts/allow-firewall.sh
# Undo:   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --blockapp <path>

set -euo pipefail

FW=/usr/libexec/ApplicationFirewall/socketfilterfw
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$FW" ]]; then
  echo "error: this script is macOS-only ($FW not found)" >&2
  exit 1
fi

# Resolve symlinks so firewall rules use the actual executable paths.
resolve() {
  python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null || echo "$1"
}

TARGETS=()

if NODE_BIN="$(command -v node 2>/dev/null)"; then
  TARGETS+=("$(resolve "$NODE_BIN")")
else
  echo "warning: node not on PATH — install it first, then re-run" >&2
fi

VENV_PY="$REPO_ROOT/backend/.venv/bin/python3"
if [[ -x "$VENV_PY" ]]; then
  # Allow both the venv executable and its base interpreter.
  TARGETS+=("$VENV_PY")
  BASE_PY="$("$VENV_PY" -c 'import sys,os; print(os.path.realpath(sys.base_prefix + "/bin/python" + ".".join(map(str, sys.version_info[:2]))))' 2>/dev/null || true)"
  [[ -n "$BASE_PY" && -x "$BASE_PY" ]] && TARGETS+=("$BASE_PY")
else
  echo "warning: $VENV_PY not found — create the venv first, then re-run" >&2
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "nothing to do" >&2
  exit 1
fi

echo "Will allow incoming connections for:"
printf '  %s\n' "${TARGETS[@]}"
echo
echo "This needs admin rights; you will be prompted for your password."
echo

for BIN in "${TARGETS[@]}"; do
  sudo "$FW" --add "$BIN" >/dev/null
  sudo "$FW" --unblockapp "$BIN" >/dev/null
  echo "  allowed: $BIN"
done

echo
echo "Done. Verify with:"
echo "  curl -s http://\$(ipconfig getifaddr en0):8000/healthz"
