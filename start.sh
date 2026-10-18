#!/usr/bin/env bash
set -euo pipefail
LDWM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$LDWM_DIR/scripts/start.py" "$@"
