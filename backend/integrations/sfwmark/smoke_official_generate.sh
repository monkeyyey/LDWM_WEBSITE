#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${PROJECT_ROOT}"

python backend/integrations/sfwmark/run_official_generate.py \
  --prompt "a clean product photo of a ceramic mug on a desk" \
  --wm-type HSQR \
  --job-id official-smoke-test

echo "Generated image:"
echo "${PROJECT_ROOT}/backend/storage/outputs/official-smoke-test/watermarked.png"
