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
