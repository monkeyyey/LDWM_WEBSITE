# The Watermarking Library

The Watermarking Library brings 14 latent-domain image watermarking methods into
one interface. It lets you generate watermarked images, inspect each method's
generation history, and run the analysis actions that method actually supports.
The aim is to compare and use published methods in a consistent workspace, not
to replace their algorithms with a single generic watermarking procedure.

## How the system works

The React frontend in `watermark-lab/` presents the methods, their variants,
options, generated images, and results. The Python API in `backend/` validates
requests, stores generation jobs under `backend/storage/outputs/`, and dispatches
each job to an integration runner. Runners use the relevant upstream source
checkout in `work/repos/`, its own Python environment, and the required model
weights. The interface does not perform the watermark computation itself.

| Category | Methods | Core idea |
| --- | --- | --- |
| Latent / initial noise | SFWMark, Gaussian-Shannon, Gaussian Shading, PRC-Watermark, Tree-Ring, Ring-ID, WIND, T2SMark | The starting noise or its frequency/code structure |
| VAE / decoder | LaWa | The image decoder used during generation |
| Dual domain / semantic | GaussMarker, SEAL | Spatial/frequency signals or semantic-aware keys |
| Optimization / tamper aware | ROBIN, TAG-WM | Optimized generation state or a trainable watermark component |
| Learned detector | SERUM | A noise-grid watermark evaluated with a trained latent detector |

**Generation** produces a watermarked image and, where needed, private state for
later analysis. **Verification** tests a specified watermark, key, or message
against an image. **Detection** asks whether the method's watermark is present;
**decoding** recovers the information its code supports. **Identification**
compares candidates to find a matching assigned watermark. Some methods also
localize tampering. These are distinct actions: a method only shows the ones its
integration supports. Results and required inputs remain method-specific.

Generation history is separated by method and variant. Select a matching source
job when an analysis needs its saved state; a job from another method is not an
interchangeable key. The image shown and offered for download is the watermarked
output, not a separate unwatermarked comparison image.

## Startup guide

### Start an existing installation

From the project root, with setup already completed on this machine:

```bash
cd /path/to/LDWM_WEBSITE
bash start.sh
```

Open <http://127.0.0.1:5173>. The API is at <http://127.0.0.1:8000>; check
<http://127.0.0.1:8000/health> if the frontend cannot reach it. Keep the
terminal open, and press Ctrl+C to stop both services. Setup is normally a
one-time step; rerun it after adding methods, changing dependencies, or moving
model artifacts. The launcher reads `.env.gpu` automatically, so you do not
need to export the runtime paths in every shell.

To use different ports, run
`bash start.sh --backend-port 8001 --frontend-port 5174`.
To start only one service, use `--backend-only` or `--frontend-only`.
The launcher runs in the foreground; use `tmux` across SSH disconnects or a
service manager for reboot persistence.

### First-time setup

Full inference requires **Linux x86_64 with an NVIDIA CUDA GPU**. On Windows,
use Ubuntu under WSL2 with NVIDIA GPU support. A Mac can run the frontend
against a reachable Linux GPU backend, but not these CUDA methods locally.
Python 3.10+ and Git are required to launch setup; Node and the method-specific
Python environments are installed or prepared by the setup tool on Linux. On a
Mac, install Node.js 22.12+ before running `--ui-only`.

For a frontend and API workspace without local GPU inference:

```bash
git clone https://github.com/monkeyyey/LDWM_WEBSITE.git
cd LDWM_WEBSITE
bash setup.sh --ui-only
bash start.sh
```

The catalogue will load, but generation and analysis need configured method
runtimes on a GPU host. To connect a frontend-only installation to a remote
backend, start it with an API address reachable from the browser:

```bash
bash start.sh --frontend-only --api-url http://127.0.0.1:8000
```

For a GPU installation, install the OS prerequisites below, then run setup as
the **same regular user** who will start the application:

```bash
git clone https://github.com/monkeyyey/LDWM_WEBSITE.git
cd LDWM_WEBSITE
bash setup.sh --plan
bash setup.sh --artifacts /absolute/path/to/ldwm-artifacts --download-models
bash start.sh
```

The artifact directory is an unpacked bundle containing `manifest.json` and
the required trained files. If you are installing only methods without supplied
artifacts, use this setup command instead:

```bash
bash setup.sh --methods tree-ring,ring-id --download-models
```

`--download-models` prefetches model weights; without it, some models
download on first use. Setup checks imports, CUDA, and artifact paths, but a
successful check is **not** an end-to-end inference test. Generate an image and
run each available analysis action before treating a deployment as validated.

### GPU host prerequisites

A working NVIDIA driver and `nvidia-smi` are prerequisites on the GPU host.

On Ubuntu 24.04, install OS prerequisites once:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv build-essential pkg-config \
  libgl1 libglib2.0-0t64 libzbar0t64 libmagic1t64 ffmpeg xz-utils ca-certificates
```

Use `sudo` only for OS packages. Installing the application as `root` can leave
runtime paths under `/root` that the backend user cannot access.
On Ubuntu 22.04, use `libglib2.0-0`, `libzbar0` and `libmagic1` without the `t64`
suffix instead.

For a persistent EC2 deployment, see the
[deployment guide](docs/AWS_SETUP_AND_MAINTENANCE.md).

Setup installs uv and Node 22 locally when needed, downloads compatible Python
interpreters, installs explicit CUDA PyTorch wheels, clones pinned upstream
sources, installs frontend dependencies from its lockfile, and builds the UI.
It writes `.env.gpu` with this machine's paths. Existing settings are preserved;
when the file changes, its previous contents are backed up privately.

`--artifacts` points to an **unpacked directory containing `manifest.json`** and
the supplied trained files. Keep this directory after installation: the config
references those files in place. Every imported checkpoint is checked against its
manifest SHA-256. The bundle must come from a trusted distributor; a checksum
detects changed files but does not authenticate who supplied it.

Trained files are not currently included in Git. To assemble a bundle from your
working GPU installation, follow the export instructions below. Users receiving
matching pretrained artifacts do **not** need to train anything.

## Install selected methods

The full collection has ten dependency groups and can use substantial disk space.
For a remote server, run the lengthy installation inside tmux as well. Rerunning
setup reuses installed environments and download caches after an interruption.
You can start with a smaller set:

```bash
bash setup.sh --methods tree-ring,ring-id --download-models
bash setup.sh --methods gaussmarker,robin --artifacts /path/to/ldwm-artifacts
bash setup.sh --methods serum --artifacts /path/to/ldwm-artifacts
```

| Runtime | Methods | Python |
| --- | --- | --- |
| `sfwmark` | SFWMark | 3.10 |
| `gaussian-shannon` | Gaussian-Shannon | 3.12 |
| `lawa` | LaWa | 3.8 |
| `gaussian-shading` | Gaussian Shading | 3.10 |
| `prc-watermark` | PRC-Watermark | 3.11 |
| `legacy` | Tree-Ring, Ring-ID, GaussMarker, ROBIN | 3.10 |
| `wind` | WIND, SEAL | 3.10 |
| `t2s` | T2SMark | 3.10 |
| `tag` | TAG-WM | 3.10 |
| `serum` | SERUM | 3.10 |

Installer-managed environments are in `.venvs/`, interpreters/tools in `.tools/`,
and sources in `work/repos/`. Existing custom `*_PYTHON` paths are reused and
checked without installing packages into those external environments. Existing
checkouts with another revision or modified tracked files are left untouched and
reported. Use a new clone or an explicit `*_REPO` override for a clean pinned copy.

## Trained artifact bundle

| Method | Files to supply |
| --- | --- |
| LaWa | Modified decoder, original KL-f8 first-stage checkpoint, SD v1.4 checkpoint |
| GaussMarker | W1 artifact and its matching trained Gaussian Noise Restorer |
| ROBIN | Optimized checkpoint containing `opt_wm` and `opt_acond` |
| TAG-WM trainable | Official DVRD checkpoint; trainfree needs none |
| SERUM | Matching YAML config, watermark grid, trained detector |

Other methods do not require a locally trained watermark checkpoint. They still
require their diffusion models; SEAL also needs BLIP-2 and its sentence encoder.
Model access permissions must be arranged with the model provider. Authenticate
through Hugging Face on the machine when required; never publish access tokens.
`--download-models` caches diffusion and SEAL models. Some upstream tools also
fetch CLIP/torchvision assets on their first run, so this is not an offline bundle.

On the working server, keep the artifact paths in `.env.gpu`, then export:

```bash
cd /home/ubuntu/LDWM_WEBSITE
bash setup.sh --export-artifacts /home/ubuntu/ldwm-artifacts
```

The export copies only the ten configured artifact files and records hashes and
source revisions. It excludes tokens, virtual environments, generated-job keys,
datasets and image history. Use `--methods gaussmarker,robin,serum` to export only
those artifacts. An export fails before copying if a selected file is missing;
TAG-WM is optional for installation, but include DVRD when exporting its trainable
variant. Share only artifacts whose redistribution terms permit it.

SERUM's supplied YAML is copied into `work/config/serum.yaml` at installation,
with a local experiment directory. A model folder from the original machine
cannot transfer by filename alone: set `WATERMARK_SERUM_MODEL_ID` to the matching
accessible model before installing if necessary. An artifact trained only in the
small SERUM smoke test remains a smoke-test artifact; packaging it does not
establish detector accuracy.

## Configure and check

The gateway and setup tools read `.env.gpu` automatically. Process environment
values take precedence. [`.env.gpu.example`](.env.gpu.example) lists the settings;
normally setup generates them without requiring you to copy the template.
Systemd can also use the generated file through `EnvironmentFile`.

```bash
bash setup.sh --methods tree-ring,ring-id --check
bash setup.sh --check
```

Setup exits with status 2 when method checks fail. Missing TAG-WM DVRD is reported
as trainfree-only availability, rather than disabling that mode. Checks cover
source revisions, imports, CUDA and artifact paths. They **do not run inference**.
Test generation and every available analysis action for each method, including
analysis after restarting the backend, before claiming a validated deployment.
See [method requirements and GPU acceptance checks](docs/REPOSITORY_METHOD_SETUP.md).

Exact installed package versions are saved under `work/setup/*.freeze.txt`.
The requirements pin the main runtime packages, but are not complete, independently
GPU-validated lockfiles for every machine. The NVIDIA driver must support all
selected CUDA wheel versions.

## Frontend on a Mac

Install Python 3.10+ and Node 22.12+ on the Mac, then:

```bash
bash setup.sh --ui-only
bash start.sh --frontend-only --api-url http://127.0.0.1:8000
```

The API URL must be reachable from the browser. An SSH tunnel to the GPU server
can expose its local port 8000 on the Mac. Ports can be changed with
`--backend-port 8001 --frontend-port 5174`; the launcher updates the frontend API
address. Keep the API behind authenticated access when deploying publicly; it
currently has no built-in user accounts or resource-aware GPU queue. Run one
GPU job at a time. Preserve `backend/storage/outputs/` for linked image analysis.

## Development checks

```bash
python3 -m unittest discover -s backend/tests -v
npm --prefix watermark-lab run build
npm --prefix watermark-lab run lint
```
