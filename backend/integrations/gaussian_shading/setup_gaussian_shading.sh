#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_DIR="${WATERMARK_GSHADING_REPO:-${PROJECT_ROOT}/work/repos/Gaussian-Shading}"
ENV_NAME="${WATERMARK_GSHADING_ENV:-gaussian-shading}"
VENV_DIR="${WATERMARK_GSHADING_VENV:-${PROJECT_ROOT}/.venv-gaussian-shading}"

CONDA_BIN="${CONDA_EXE:-}"
if [ -z "${CONDA_BIN}" ]; then
  for candidate in "$(command -v conda 2>/dev/null || true)" /home/ubuntu/miniconda3/bin/conda; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then CONDA_BIN="${candidate}"; break; fi
  done
fi

if [ -n "${CONDA_BIN}" ]; then
  if ! "${CONDA_BIN}" env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
    "${CONDA_BIN}" create --override-channels -c conda-forge -n "${ENV_NAME}" python=3.10 -y
  fi
  run_python() { "${CONDA_BIN}" run -n "${ENV_NAME}" python "$@"; }
  PYTHON_PATH="$(run_python -c 'import sys; print(sys.executable)')"
else
  BOOTSTRAP_PYTHON="${WATERMARK_GSHADING_BOOTSTRAP_PYTHON:-$(command -v python3.10 2>/dev/null || true)}"
  if [ -z "${BOOTSTRAP_PYTHON}" ]; then
    echo "Python 3.10 or Miniconda is required for the upstream Gaussian Shading runtime." >&2
    exit 1
  fi
  [ -x "${VENV_DIR}/bin/python" ] || "${BOOTSTRAP_PYTHON}" -m venv "${VENV_DIR}"
  run_python() { "${VENV_DIR}/bin/python" "$@"; }
  PYTHON_PATH="${VENV_DIR}/bin/python"
fi

mkdir -p "$(dirname "${REPO_DIR}")"
if [ ! -d "${REPO_DIR}/.git" ]; then
  git clone https://github.com/bsmhmmlf/Gaussian-Shading.git "${REPO_DIR}"
fi

run_python -m pip install --upgrade pip setuptools wheel
run_python -m pip install torch==1.13.1+cu117 torchvision==0.14.1+cu117 --index-url https://download.pytorch.org/whl/cu117
# The web runtime does not use the upstream bulk-evaluation dataset loader.
# Tokenizers 0.14.1 requires huggingface_hub < 0.18, so keep this stack together.
run_python -m pip install \
  diffusers==0.11.1 transformers==4.34.0 tokenizers==0.14.1 huggingface_hub==0.17.3 \
  accelerate==0.23.0 safetensors==0.3.3 numpy==1.24.4 scipy==1.10.1 Pillow==9.5.0 matplotlib==3.7.5 \
  pycryptodome==3.20.0 tqdm==4.66.2

run_python - <<'PY'
import diffusers, torch
from Crypto.Cipher import ChaCha20
print("torch:", torch.__version__)
print("diffusers:", diffusers.__version__)
print("cuda:", torch.cuda.is_available())
if torch.cuda.is_available(): print("gpu:", torch.cuda.get_device_name(0))
PY

echo "Gaussian Shading environment ready. Add these values to the backend EnvironmentFile:"
echo "WATERMARK_GSHADING_REPO=${REPO_DIR}"
echo "WATERMARK_GSHADING_PYTHON=${PYTHON_PATH}"
echo "WATERMARK_GSHADING_MODEL_ID=sd2-community/stable-diffusion-2-1-base"
