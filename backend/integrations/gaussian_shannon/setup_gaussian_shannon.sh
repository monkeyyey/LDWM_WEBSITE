#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GS_DIR="${WATERMARK_GS_REPO:-${PROJECT_ROOT}/work/repos/Gaussian-Shannon}"
ENV_NAME="${WATERMARK_GS_ENV:-gaussian-shannon}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required. Use an AWS Deep Learning AMI or install Miniconda first." >&2
  exit 1
fi

mkdir -p "$(dirname "${GS_DIR}")"
if [ ! -d "${GS_DIR}/.git" ]; then
  git clone https://github.com/Rambo-Yi/Gaussian-Shannon.git "${GS_DIR}"
fi

if ! conda env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
  conda create -n "${ENV_NAME}" python=3.12 -y
fi

conda run -n "${ENV_NAME}" python -m pip install --upgrade pip

# Keep the upstream torch/torchvision versions, but install the CUDA 12.4
# wheels explicitly so the environment can use the EC2 GPU.
FILTERED_REQ="$(mktemp)"
trap 'rm -f "${FILTERED_REQ}"' EXIT
grep -vE '^(torch==|torchvision==)' "${GS_DIR}/requirements.txt" > "${FILTERED_REQ}"
conda run -n "${ENV_NAME}" python -m pip install \
  torch==2.5.1 torchvision==0.20.1 \
  --index-url https://download.pytorch.org/whl/cu124
conda run -n "${ENV_NAME}" python -m pip install -r "${FILTERED_REQ}"

conda run -n "${ENV_NAME}" python - <<'PY'
import sys
import torch
import diffusers

print("python:", sys.executable)
print("torch:", torch.__version__)
print("diffusers:", diffusers.__version__)
print("cuda:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY

echo
echo "Gaussian-Shannon environment ready. Start the backend with:"
echo "export WATERMARK_GS_REPO=${GS_DIR}"
echo "export WATERMARK_GS_PYTHON=\$(conda run -n ${ENV_NAME} which python)"
