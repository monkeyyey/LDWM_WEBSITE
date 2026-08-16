# Unified Watermark Backend

This backend is an API gateway over five repository-specific implementations:

```text
frontend -> normalized API -> method adapter -> repository runner
```

The adapters do not invent a common watermark algorithm. They translate the
shared request into the original SFWMark, Gaussian-Shannon, LaWa, Gaussian
Shading, or PRC-Watermark workflow, run it in that repository's environment,
and normalize its output.

## Run

```bash
python3 backend/server.py --port 8000
```

Useful checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/methods
```

The frontend runs separately:

```bash
cd watermark-lab
pnpm install
pnpm dev
```

## API

```text
GET  /health
GET  /methods
GET  /jobs              # generated jobs; filter with ?method=...&submethod=...
POST /watermark/generate
POST /detect
GET  /files/<path>      # generated watermarked images and job artifacts
```

All POST requests use the same fields where applicable:

```json
{
  "method": "sfwmark",
  "submethodId": "hsqr",
  "analysisMode": "verify",
  "prompt": "a ceramic mug on a desk",
  "message": "HSQR",
  "seed": 42,
  "imageDataUrl": null,
  "sourceJobId": null,
  "options": {}
}
```

There is no generic post-hoc watermark upload operation. The selected
repositories watermark during generation; analysis accepts a generated or
edited image and runs that repository's extraction/detection path.

## Workflow Mapping

The website presents the same three conceptual actions for every method:

- **Generation** creates the watermarked image using the repository's native
  generation path.
- **Verification** maps to the repository's actual analysis: SFWMark compares
  the inverted latent with the expected Fourier pattern; Gaussian-Shannon and
  LaWa extract the message and report bit-level recovery.
- **Gaussian Shading verification** decrypts and majority-votes the inverted
  latent, then reports bit accuracy, BER, and the repository's separate
  detection and multi-user traceability threshold decisions.
- **PRC-Watermark verification** reports the released repository's statistical
  `Detect` result, whether `Decode` returned a valid payload, and their
  OR-combined binary decision.
- **Identification** is available for SFWMark only. It searches the 2048-pattern
  candidate bank and compares the predicted index with the ground-truth index.
  Gaussian-Shannon, LaWa, Gaussian Shading, and PRC-Watermark do not provide a
  candidate-bank identification workflow, so the UI leaves that action
  unavailable for those methods.

The API surface is limited to the repository-backed generation and analysis
workflows described above. It does not advertise secondary attack or quality
experiments as product actions.

Generation history is stored per method and submethod. For example:

```text
GET /jobs?method=gaussian-shannon&submethod=ldpc
GET /jobs?method=lawa&submethod=lawa-48
GET /jobs?method=sfwmark&submethod=hsqr
GET /jobs?method=gaussian-shading&submethod=chacha
GET /jobs?method=prc-watermark&submethod=prc
```

An analysis request may use the selected generation's `sourceJobId`. The
source job identifies the compatible image and repository artifacts; it is not
interchangeable across methods or submethods.

## Repository Environments

Each method needs its own Python environment, model weights, and usually a GPU.
The adapter reports `setup_required` when those prerequisites are missing; it
does not report a synthetic completed result.

- `SFWMARK_REPO`: optional SFWMark checkout override.
- `SFWMARK_PYTHON`: Python executable for the SFWMark environment.
- `WATERMARK_GS_PYTHON`: Python executable for Gaussian-Shannon.
- `WATERMARK_GS_REPO`: optional Gaussian-Shannon checkout override.
- `WATERMARK_GS_MODEL_ID`: optional Hugging Face model override; the default is
  `sd2-community/stable-diffusion-2-1-base`, a currently available Diffusers
  Stable Diffusion 2.1-base checkpoint.
- `WATERMARK_LAWA_PYTHON`: Python executable for LaWa.
- `WATERMARK_DEVICE`: optional Torch device override for Gaussian-Shannon.
- `WATERMARK_GSHADING_REPO`: optional Gaussian Shading checkout override.
- `WATERMARK_GSHADING_PYTHON`: Python executable for Gaussian Shading.
- `WATERMARK_GSHADING_MODEL_ID`: optional model override for Gaussian Shading.
- `WATERMARK_PRC_REPO`: optional PRC-Watermark checkout override.
- `WATERMARK_PRC_PYTHON`: Python executable for PRC-Watermark.
- `WATERMARK_PRC_MODEL_ID`: optional model override for PRC-Watermark.

The checked-out repositories expected by the default configuration are:

```text
work/repos/SFWMark
work/repos/Gaussian-Shannon
work/repos/LaWa
work/repos/Gaussian-Shading
work/repos/PRC-Watermark
```

Gaussian-Shannon setup can be prepared with. Conda is used when available;
otherwise the helper creates `.venv-gaussian-shannon` automatically:

```bash
bash backend/integrations/gaussian_shannon/setup_gaussian_shannon.sh
export WATERMARK_GS_REPO="$PWD/work/repos/Gaussian-Shannon"
```

The setup command prints the correct `WATERMARK_GS_PYTHON` export for the
runtime it selected.

The runner preserves the upstream defaults: Gaussian coding uses redundancy
64, LDPC coding uses redundancy 16, and generation uses float32 latent values.
The setup helper resolves an upstream dependency conflict by using NumPy 1.26.4
with Matplotlib 3.8.2; override it with `WATERMARK_GS_NUMPY_VERSION` only when
you have tested a compatible version. It also installs the Diffusers runtime
companions `transformers`, `accelerate`, and `safetensors`, which are not all
listed by the upstream requirements file.

Setup helpers for SFWMark live in
`backend/integrations/sfwmark/setup_sfwmark.sh`. The direct smoke scripts in
that directory exercise official generation and detection without the browser.

Gaussian Shading and PRC-Watermark use isolated environments because their
upstream Diffusers and Torch versions differ from the other methods:

```bash
bash backend/integrations/gaussian_shading/setup_gaussian_shading.sh
bash backend/integrations/prc_watermark/setup_prc_watermark.sh
```

Each helper prints the repository, Python, and model environment values to add
to the backend systemd `EnvironmentFile`.

## SFWMark Output Contract

Generation stores only the watermarked image for display. It also keeps the
pattern bank, ground-truth index, and metadata needed by the repository-backed
verification and identification actions. A clean comparison image is not
served by the API.

The SFWMark single-image adapter reports both analyses from the original
repository logic:

- verification distance to the known ground-truth pattern;
- identification by `argmin` over the candidate bank, followed by accuracy
  scoring against the stored ground-truth index.

The original repository's full verification evaluation is a dataset-level ROC
experiment. The website's one-image action exposes its underlying distance for
the selected generated job, not a fabricated ROC score.
