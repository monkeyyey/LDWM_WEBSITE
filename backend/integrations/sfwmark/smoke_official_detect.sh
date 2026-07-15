#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${PROJECT_ROOT}"

WM_TYPE="${1:-HSQR}"
SOURCE_JOB_ID="${2:-official-smoke-${WM_TYPE}}"
IMAGE_PATH="${PROJECT_ROOT}/backend/storage/outputs/${SOURCE_JOB_ID}/watermarked.png"

if [ ! -f "${IMAGE_PATH}" ]; then
  echo "Missing ${IMAGE_PATH}"
  echo "Run: bash backend/integrations/sfwmark/smoke_official_generate.sh ${WM_TYPE} ${SOURCE_JOB_ID}"
  exit 1
fi

python backend/integrations/sfwmark/run_official_detect_single.py \
  --job-id "official-detect-${WM_TYPE}" \
  --source-job-id "${SOURCE_JOB_ID}" \
  --image-path "${IMAGE_PATH}"

echo "Detection result:"
echo "${PROJECT_ROOT}/backend/storage/outputs/official-detect-${WM_TYPE}/detect.json"
