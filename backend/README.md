# Unified Watermark Backend

This backend gives the website one stable API even though each research repo has its own environment, checkpoints, scripts, and output protocol.

## Core Idea

Do not merge every GitHub repo into one Python environment.

Use this structure instead:

```text
frontend
  -> unified backend API
    -> method adapter
      -> isolated worker/container for that repo
        -> repo-specific command, checkpoints, outputs
```

The frontend only talks to normalized endpoints. Each adapter hides the repo-specific details.

## Local Mock Server

Run:

```bash
python3 backend/server.py --port 8000
```

Check:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/methods
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/watermark/generate \
  -H 'content-type: application/json' \
  -d '{
    "method": "sfwmark",
    "prompt": "a clean product photo of a ceramic mug",
    "message": "SIT-LDW-0001",
    "seed": 42,
    "strength": 68,
    "attack": "None"
  }'
```

## Real GPU Mode on AWS

The `sfwmark` adapter now defaults to an official SFWMark generation path. On a CUDA EC2 instance, set it up with:

```bash
cd ~/1-latent-watermark-inject-and-detect
source .venv/bin/activate
bash backend/integrations/sfwmark/setup_sfwmark.sh
```

Check CUDA:

```bash
python3 - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda")
PY
```

Check backend runtime diagnostics:

```bash
python3 backend/server.py --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/runtime
```

Run a direct official SFWMark generation smoke test without the browser:

```bash
bash backend/integrations/sfwmark/smoke_official_generate.sh
```

If this succeeds, it writes:

```text
backend/storage/outputs/official-smoke-test/watermarked.png
```

If it fails, the printed logs should say whether the issue is missing packages, CUDA, Hugging Face model access, or another runtime error.

If you want to use the lightweight built-in fallback instead of the official SFWMark repo path:

```bash
SFWMARK_OFFICIAL=0 python3 backend/server.py --host 0.0.0.0 --port 8000
```

Start the backend:

```bash
python3 backend/server.py --host 0.0.0.0 --port 8000
```

Start the frontend:

```bash
cd watermark-lab
npm install
npm run dev -- --host 0.0.0.0
```

Open:

```text
http://<EC2_PUBLIC_IP>:5173
```

The real functional path is currently:

```text
SFWMark -> Generate Watermarked Image
```

It runs the official SFWMark `src/generate.py` against a one-prompt DB1k-compatible dataset, copies the generated watermarked image into backend storage, and returns it to the website preview.

Gaussian Shannon and LaWa still need their heavier repo-specific environments/checkpoints before they can run real inference.

## Normalized Endpoints

```text
GET  /health
GET  /methods
POST /watermark/upload
POST /watermark/generate
POST /detect
POST /attack-test
```

## What Each Adapter Must Do

Each adapter should:

- validate whether the method supports the requested workflow
- map normalized fields into repo-specific CLI arguments
- create a per-job working directory
- call the repo inside its own environment/container
- collect output images, CSV files, scores, and recovered bits
- return the shared `WatermarkResult` shape

## Why This Works

The repositories can keep their own:

- Python version
- PyTorch/CUDA version
- conda or pip dependencies
- checkpoint layout
- command-line scripts
- attack/evaluation protocol

The website still sees one unified product.

## Recommended Production Shape

Use the local server as an API gateway, then replace mock adapters with job submissions:

```text
watermark-api
redis queue
sfwmark-worker
gaussian-shannon-worker
lawa-worker
object storage for images/results
postgres/sqlite for job metadata
```

For cloud deployment, each worker should be built from a separate Dockerfile because the environments conflict.
