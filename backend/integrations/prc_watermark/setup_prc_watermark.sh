#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_DIR="${WATERMARK_PRC_REPO:-${PROJECT_ROOT}/work/repos/PRC-Watermark}"
ENV_NAME="${WATERMARK_PRC_ENV:-prc-watermark}"
VENV_DIR="${WATERMARK_PRC_VENV:-${PROJECT_ROOT}/.venv-prc-watermark}"

CONDA_BIN="${CONDA_EXE:-}"
if [ -z "${CONDA_BIN}" ]; then
  for candidate in "$(command -v conda 2>/dev/null || true)" /home/ubuntu/miniconda3/bin/conda; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then CONDA_BIN="${candidate}"; break; fi
  done
fi

if [ -n "${CONDA_BIN}" ]; then
  if ! "${CONDA_BIN}" env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
    "${CONDA_BIN}" create --override-channels -c conda-forge -n "${ENV_NAME}" python=3.11 -y
  fi
  run_python() { "${CONDA_BIN}" run -n "${ENV_NAME}" python "$@"; }
  PYTHON_PATH="$(run_python -c 'import sys; print(sys.executable)')"
else
  BOOTSTRAP_PYTHON="${WATERMARK_PRC_BOOTSTRAP_PYTHON:-$(command -v python3.11 2>/dev/null || true)}"
  if [ -z "${BOOTSTRAP_PYTHON}" ]; then
    echo "Python 3.11 or Miniconda is required for the upstream PRC-Watermark runtime." >&2
    exit 1
  fi
  [ -x "${VENV_DIR}/bin/python" ] || "${BOOTSTRAP_PYTHON}" -m venv "${VENV_DIR}"
  run_python() { "${VENV_DIR}/bin/python" "$@"; }
  PYTHON_PATH="${VENV_DIR}/bin/python"
fi

mkdir -p "$(dirname "${REPO_DIR}")"
if [ ! -d "${REPO_DIR}/.git" ]; then
  git clone https://github.com/XuandongZhao/PRC-Watermark.git "${REPO_DIR}"
fi

run_python -m pip install --upgrade pip setuptools wheel
run_python -m pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121
run_python -m pip install \
  diffusers==0.21.4 transformers==4.29.2 huggingface_hub==0.25.0 accelerate \
  numpy==1.26.0 scipy galois==0.4.1 ldpc==0.1.51 datasets Pillow tqdm

run_python - <<'PY'
import diffusers, galois, ldpc, torch
print("torch:", torch.__version__)
print("diffusers:", diffusers.__version__)
print("cuda:", torch.cuda.is_available())
if torch.cuda.is_available(): print("gpu:", torch.cuda.get_device_name(0))
PY

echo "PRC-Watermark environment ready. Add these values to the backend EnvironmentFile:"
echo "WATERMARK_PRC_REPO=${REPO_DIR}"
echo "WATERMARK_PRC_PYTHON=${PYTHON_PATH}"
echo "WATERMARK_PRC_MODEL_ID=sd2-community/stable-diffusion-2-1-base"
