#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${PROJECT_ROOT}"

for WM_TYPE in HSQR HSTR Tree-Ring RingID; do
  JOB_ID="official-smoke-${WM_TYPE}"
  echo "==> Generating ${WM_TYPE}"
  bash backend/integrations/sfwmark/smoke_official_generate.sh "${WM_TYPE}" "${JOB_ID}"
  echo "==> Detecting ${WM_TYPE}"
  bash backend/integrations/sfwmark/smoke_official_detect.sh "${WM_TYPE}" "${JOB_ID}"
done

echo "All SFWMark watermark type smoke tests completed."
