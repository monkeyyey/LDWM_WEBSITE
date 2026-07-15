#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
EXTERNAL_DIR="${PROJECT_ROOT}/external"
SFW_DIR="${EXTERNAL_DIR}/SFWMark"

mkdir -p "${EXTERNAL_DIR}"

if command -v sudo >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y git libgl1 libglib2.0-0
  sudo apt-get install -y libzbar0 || sudo apt-get install -y libzbar0t64
fi

if [ ! -d "${SFW_DIR}/.git" ]; then
  git clone https://github.com/thomas11809/SFWMark.git "${SFW_DIR}"
else
  git -C "${SFW_DIR}" pull --ff-only
fi

python -m pip install --upgrade pip

# The AWS Deep Learning AMI already provides a CUDA-enabled torch build.
# Do not let SFWMark's requirements replace it with a different CUDA wheel.
FILTERED_REQ="$(mktemp)"
grep -vE '^(--extra-index-url|torch==|torchvision==)' "${SFW_DIR}/requirements.txt" > "${FILTERED_REQ}"
python -m pip install -r "${FILTERED_REQ}"
rm -f "${FILTERED_REQ}"

# The upstream SFWMark requirements currently miss a few imports used by
# src/utils.py and src/generate.py. Keep these explicit so the smoke test
# fails on model/runtime issues instead of missing utility packages.
python -m pip install "qrcode[pil]" pyzbar tqdm "huggingface_hub[cli]>=0.24.0,<1.0"

python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda:", torch.cuda.is_available())
print("gpu:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")
PY

echo "SFWMark ready at ${SFW_DIR}"
