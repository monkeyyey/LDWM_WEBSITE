#!/usr/bin/env bash
set -euo pipefail
LDWM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "$LDWM_DIR/setup.sh" --methods gaussian-shading "$@"
