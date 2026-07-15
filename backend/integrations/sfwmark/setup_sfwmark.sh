#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
EXTERNAL_DIR="${PROJECT_ROOT}/external"
SFW_DIR="${EXTERNAL_DIR}/SFWMark"

mkdir -p "${EXTERNAL_DIR}"

if [ ! -d "${SFW_DIR}/.git" ]; then
  git clone https://github.com/thomas11809/SFWMark.git "${SFW_DIR}"
else
  git -C "${SFW_DIR}" pull --ff-only
fi

python -m pip install --upgrade pip
python -m pip install -r "${SFW_DIR}/requirements.txt"

echo "SFWMark ready at ${SFW_DIR}"
