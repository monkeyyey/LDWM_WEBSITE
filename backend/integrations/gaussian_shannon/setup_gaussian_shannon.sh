#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GS_DIR="${WATERMARK_GS_REPO:-${PROJECT_ROOT}/work/repos/Gaussian-Shannon}"
ENV_NAME="${WATERMARK_GS_ENV:-gaussian-shannon}"
VENV_DIR="${WATERMARK_GS_VENV:-${PROJECT_ROOT}/.venv-gaussian-shannon}"

if command -v conda >/dev/null 2>&1; then
  RUNTIME="conda"
  if ! conda env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
    # Use conda-forge explicitly so setup does not depend on Anaconda's
    # interactive channel Terms of Service acceptance.
    conda create --override-channels -c conda-forge -n "${ENV_NAME}" python=3.12 -y
  fi
  run_python() { conda run -n "${ENV_NAME}" python "$@"; }
  PYTHON_PATH="$(run_python -c 'import sys; print(sys.executable)')"
else
  RUNTIME="venv"
  if [ ! -x "${VENV_DIR}/bin/python" ]; then
    BOOTSTRAP_PYTHON="${WATERMARK_GS_BOOTSTRAP_PYTHON:-}"
    if [ -z "${BOOTSTRAP_PYTHON}" ]; then
      for candidate in python3.12 python3; do
        if command -v "${candidate}" >/dev/null 2>&1; then
          BOOTSTRAP_PYTHON="$(command -v "${candidate}")"
          break
        fi
      done
    fi
    if [ -z "${BOOTSTRAP_PYTHON}" ]; then
      echo "Python 3.12 or python3 is required to create ${VENV_DIR}." >&2
      echo "Install it with: sudo apt-get install -y python3-venv python3-pip" >&2
      exit 1
    fi
    "${BOOTSTRAP_PYTHON}" -m venv "${VENV_DIR}"
  fi
  run_python() { "${VENV_DIR}/bin/python" "$@"; }
  PYTHON_PATH="${VENV_DIR}/bin/python"
fi

mkdir -p "$(dirname "${GS_DIR}")"
if [ ! -d "${GS_DIR}/.git" ]; then
  git clone https://github.com/Rambo-Yi/Gaussian-Shannon.git "${GS_DIR}"
fi

run_python -m pip install --upgrade pip

# Keep the upstream torch/torchvision versions, but install the CUDA 12.4
# wheels explicitly so the environment can use the EC2 GPU.
FILTERED_REQ="$(mktemp)"
trap 'rm -f "${FILTERED_REQ}" "${FILTERED_REQ}.rest"' EXIT
grep -vE '^(torch==|torchvision==)' "${GS_DIR}/requirements.txt" > "${FILTERED_REQ}"
run_python -m pip install \
  torch==2.5.1 torchvision==0.20.1 \
  --index-url https://download.pytorch.org/whl/cu124

# The upstream requirements pin matplotlib 3.8.2 (which requires numpy<2) while
# also pinning an incompatible numpy 2.x release. Use the latest stable 1.x
# wheel supported by Python 3.12; it satisfies the rest of this environment.
# pyldpc 0.7.9 imports NumPy from setup.py without declaring it as a build
# requirement, so install the prerequisite first and disable build isolation.
NUMPY_VERSION="${WATERMARK_GS_NUMPY_VERSION:-1.26.4}"
run_python -m pip install "numpy==${NUMPY_VERSION}" setuptools wheel
run_python -m pip install --no-build-isolation "pyldpc==0.7.9"
grep -vE '^(numpy==|pyldpc==)' "${FILTERED_REQ}" > "${FILTERED_REQ}.rest"
run_python -m pip install -r "${FILTERED_REQ}.rest"

run_python - <<'PY'
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
echo "Gaussian-Shannon environment ready via ${RUNTIME}. Start the backend with:"
echo "export WATERMARK_GS_REPO=${GS_DIR}"
if [ "${RUNTIME}" = "conda" ]; then
  echo "export WATERMARK_GS_PYTHON=\$(conda run -n ${ENV_NAME} which python)"
else
  echo "export WATERMARK_GS_PYTHON=${PYTHON_PATH}"
fi
