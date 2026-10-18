#!/usr/bin/env bash
set -euo pipefail
LDWM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.10 or newer, then run this setup again." >&2
  exit 1
fi
exec python3 "$LDWM_DIR/scripts/setup.py" "$@"
