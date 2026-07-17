#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${PROJECT_ROOT}"

FAILED=0

for WM_TYPE in HSQR HSTR Tree-Ring RingID; do
  JOB_ID="official-smoke-${WM_TYPE}"
  echo "==> Generating ${WM_TYPE}"
  bash backend/integrations/sfwmark/smoke_official_generate.sh "${WM_TYPE}" "${JOB_ID}"
  echo "==> Detecting ${WM_TYPE}"
  bash backend/integrations/sfwmark/smoke_official_detect.sh "${WM_TYPE}" "${JOB_ID}"

  DETECT_JSON="${PROJECT_ROOT}/backend/storage/outputs/official-detect-${WM_TYPE}/detect.json"
  if python - "${DETECT_JSON}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not payload.get("matched"):
    print(
        f"FAIL: {payload.get('wm_type')} expected key {payload.get('key_index')} "
        f"but predicted {payload.get('predicted_index')}."
    )
    raise SystemExit(1)
print(
    f"PASS: {payload.get('wm_type')} matched key {payload.get('key_index')} "
    f"with distance {payload.get('distance'):.4f}."
)
PY
  then
    :
  else
    FAILED=1
  fi
done

if [ "${FAILED}" -eq 0 ]; then
  echo "All SFWMark watermark type smoke tests passed."
else
  echo "One or more SFWMark watermark type smoke tests failed."
  exit 1
fi
