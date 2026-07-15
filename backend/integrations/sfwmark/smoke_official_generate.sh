#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${PROJECT_ROOT}"

WM_TYPE="${1:-HSQR}"
JOB_ID="${2:-official-smoke-${WM_TYPE}}"

python backend/integrations/sfwmark/run_official_generate.py \
  --prompt "a clean product photo of a ceramic mug on a desk" \
  --wm-type "${WM_TYPE}" \
  --job-id "${JOB_ID}"

echo "Generated image:"
echo "${PROJECT_ROOT}/backend/storage/outputs/${JOB_ID}/watermarked.png"
