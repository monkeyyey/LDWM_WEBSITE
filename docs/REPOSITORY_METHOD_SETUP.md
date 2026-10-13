# Repository Method Setup and Validation

## Status and scope

Nine new **experimental inference integrations** are wired to the website, in addition to the existing five methods. They call official repository functions from pinned source checkouts, not approximations or simulated result generators.

This development machine has no NVIDIA CUDA device or diffusion model installations. Frontend and CPU contract checks are not proof of real image generation, detection quality, or paper-level reproduction. Every new method remains marked **GPU validation pending** until the acceptance checks below pass on your server.

Training, optimization, full attack sweeps, FID/CLIP evaluation, ROC calibration and multi-image benchmarking remain **offline upstream workflows**, not website buttons. Explicit differences from the upstream evaluation scripts are listed below.

## Sources reviewed

The full pinned commit is stored in `backend/config/repository_methods.json`. The runner rejects another revision or modified tracked files. Setup never resets existing checkouts.

| Method | Source | Reviewed commit | Candidate runtime profile |
| --- | --- | --- | --- |
| Tree-Ring | [Official source](https://github.com/YuxinWenRick/tree-ring-watermark/tree/3015283d9cf82e90b628f02ad2121bd37408ca9a) | `3015283d9cf8` | `legacy.txt` |
| RingID | [Official source](https://github.com/showlab/RingID/tree/45631a59aecd7d63ccdb640aaaf3e616fdb89fb9) | `45631a59aecd` | `legacy.txt` |
| WIND | [Official source](https://github.com/Kasraarabi/Hidden-in-the-Noise/tree/e923df7f74c7e41745c071d831e4b76d04665a5a) | `e923df7f74c7` | `wind.txt` |
| T2SMark | [Official source](https://github.com/0xD009/T2SMark/tree/0c1fbfd50fcd1fba135477a2c016e284d5d7914d) | `0c1fbfd50fcd` | `t2s.txt` |
| GaussMarker | [Official source](https://github.com/SunnierLee/GaussMarker/tree/4ac9bfd4e152a56bd93c2a06a809ef6ff8e73155) | `4ac9bfd4e152` | `legacy.txt` |
| SEAL | [Official source](https://github.com/Kasraarabi/SEAL/tree/92d31b31b93a6e373fe88a584c640beafb68c6fa) | `92d31b31b93a` | `seal.txt` |
| ROBIN | [Official source](https://github.com/Hannah1102/ROBIN/tree/6b2c2ddf5e50d7d75c71a41c84a7781d2826be1f) | `6b2c2ddf5e50` | `legacy.txt` |
| TAG-WM | [Official source](https://github.com/Suchenl/TAG-WM/tree/74890e38211a986aebda95c4c3dd160578632977) | `74890e38211a` | `tag.txt` |
| SERUM | [Official source](https://github.com/Hubizon/SERUM/tree/02f4929e30cd976c5cfe65a45ef1bc4ac79bdfed) | `02f4929e30cd` | `serum.txt` |

Profiles in `backend/integrations/repository_methods/requirements/` are inference-focused dependency sets, not GPU-validated lockfiles. Core diffusion versions follow upstream; compatibility pins and omitted benchmark-only packages are documented in the files. A method needs its own pinned source checkout and may need its own model or trained artifacts, but it does **not** automatically need its own Python environment. These integrations launch isolated subprocesses, so methods can share an environment when their dependency profiles are compatible. Do not combine profiles with conflicting pins just to reduce setup.

## 1. Prepare the GPU server

Use Linux with an NVIDIA GPU and Python 3.10 environments. This is not a CPU or Apple Silicon inference implementation. On Windows, use WSL2 with NVIDIA CUDA support and run these Linux commands inside WSL2.

From the project root:

```bash
nvidia-smi
python3 backend/integrations/repository_methods/setup_repositories.py --method all --clone
```

This downloads only source into `work/repos/`, not model weights. Source copies in `work/review/` are development audit copies and are not used by the backend.

Plan disk space for model caches and private job state. Ring-ID's 2,048 complex-valued patterns and WIND's 10,000-noise registry can consume substantial RAM, VRAM and disk. Start WIND full-mode validation with a small registry (e.g. 16 groups and 32 noises); increase only after checking memory. SEAL additionally loads BLIP-2 and a sentence encoder. Actual GPU memory requirements need measurement on your machine.

## 2. Create runtime environments

Start with one environment per distinct dependency profile, not one per method. The current candidate groups are:

| Environment | Methods | Requirements profile | Sharing note |
| --- | --- | --- | --- |
| `ldwm-legacy` | Tree-Ring, RingID, GaussMarker, ROBIN | `legacy.txt` | Same exact pins; GaussMarker and ROBIN still need their own trained artifacts. |
| `ldwm-wind` | WIND, SEAL | `wind.txt` plus `seal.txt` additions | `seal.txt` includes `wind.txt`, so SEAL can use this environment. |
| `ldwm-t2smark` | T2SMark | `t2s.txt` | Separate Diffusers/Transformers pins from WIND. |
| `ldwm-tag-wm` | TAG-WM | `tag.txt` | Keep separate initially because its Transformers and Hub pins differ from `legacy.txt`. |
| `ldwm-serum` | SERUM | `serum.txt` | Separate modern PyTorch/Diffusers stack. |

These are candidate groups based on the checked-in pins, not a claim that GPU inference has already been validated. If an upstream import or runtime check reveals an incompatibility, split only the affected method into its own environment. Source checkouts remain method-specific even when their Python environment is shared.

Example for the shared legacy environment, using Conda:

```bash
conda create -n ldwm-legacy python=3.10 -y
conda run -n ldwm-legacy python -m pip install -r backend/integrations/repository_methods/requirements/legacy.txt
conda run -n ldwm-legacy python -m pip check
conda run -n ldwm-legacy python -c "import sys, torch; print(sys.executable); print(torch.cuda.is_available())"
```

For SEAL, install `seal.txt` in the WIND environment; it pulls in the shared WIND pins plus SEAL's additional packages. Create the other environments from their corresponding profile in the table. `pip check` and a CUDA availability check are necessary but not sufficient: run the repository check and a real generation/detection smoke test for every method before treating a shared group as validated.

For CUDA wheel selection, follow the upstream PyTorch version and your server driver. Do not silently upgrade diffusers to resolve dependency problems: these repositories subclass older diffusion pipelines. The legacy methods use torch 1.13.0 / torchvision 0.14.0. WIND, T2SMark and SEAL use torch 2.5.0 / torchvision 0.20.0. SERUM uses torch 2.7.1 / torchvision 0.22.1; its upstream instructions specify CUDA 11.8 wheels.

Set the backend environment variables to the **absolute Python executable paths** printed by each environment. Methods in a shared group should point to the same executable:

```bash
export WATERMARK_TREE_RING_PYTHON="$(conda run -n ldwm-legacy python -c 'import sys; print(sys.executable)')"
export WATERMARK_RING_ID_PYTHON="$(conda run -n ldwm-legacy python -c 'import sys; print(sys.executable)')"
export WATERMARK_GAUSSMARKER_PYTHON="$(conda run -n ldwm-legacy python -c 'import sys; print(sys.executable)')"
export WATERMARK_ROBIN_PYTHON="$(conda run -n ldwm-legacy python -c 'import sys; print(sys.executable)')"
export WATERMARK_WIND_PYTHON="$(conda run -n ldwm-wind python -c 'import sys; print(sys.executable)')"
export WATERMARK_SEAL_PYTHON="$(conda run -n ldwm-wind python -c 'import sys; print(sys.executable)')"
export WATERMARK_T2SMARK_PYTHON="$(conda run -n ldwm-t2smark python -c 'import sys; print(sys.executable)')"
```

Add these to your backend service's environment file when deploying. The website's Python environment is independent from these shared inference environments. Do not put SSH keys or Hugging Face tokens in tracked source files.

| Method ID | Python executable variable | Optional source path override |
| --- | --- | --- |
| `tree-ring` | `WATERMARK_TREE_RING_PYTHON` | `WATERMARK_TREE_RING_REPO` |
| `ring-id` | `WATERMARK_RING_ID_PYTHON` | `WATERMARK_RING_ID_REPO` |
| `wind` | `WATERMARK_WIND_PYTHON` | `WATERMARK_WIND_REPO` |
| `t2smark` | `WATERMARK_T2SMARK_PYTHON` | `WATERMARK_T2SMARK_REPO` |
| `gaussmarker` | `WATERMARK_GAUSSMARKER_PYTHON` | `WATERMARK_GAUSSMARKER_REPO` |
| `seal` | `WATERMARK_SEAL_PYTHON` | `WATERMARK_SEAL_REPO` |
| `robin` | `WATERMARK_ROBIN_PYTHON` | `WATERMARK_ROBIN_REPO` |
| `tag-wm` | `WATERMARK_TAG_WM_PYTHON` | `WATERMARK_TAG_WM_REPO` |
| `serum` | `WATERMARK_SERUM_PYTHON` | `WATERMARK_SERUM_REPO` |

Each method also supports `WATERMARK_<METHOD>_MODEL_ID` with the same uppercase prefix, for example `WATERMARK_RING_ID_MODEL_ID`. The shared pipeline loader uses the `fp16` model revision by default; set `WATERMARK_<METHOD>_MODEL_REVISION` when the selected model repository uses a different ref (for example, `main`). Use the original SD 2.1 architecture/weights or a trusted local copy; changing to an unrelated model does not reproduce the method. T2SMark defaults to SD 2.1 (not the base variant), as in its repository. Model access/license acceptance and cache downloads must be arranged on the server. Offline model folders must contain the complete pipeline, including scheduler/tokenizer/VAE/UNet assets. SERUM instead takes its model and sampling settings from the saved SERUM YAML configuration; its generic MODEL_ID variable is not used.

## 3. Prepare method artifacts

### Tree-Ring

No trained watermark checkpoint is required. Ring, random and zero Fourier patterns are available. Generation saves the actual pattern and mask; detection inverts the image with an empty prompt and reports the native L1 Fourier distance. The UI supports the published circle/complex-injection baseline, not every experimental pattern/mask combination.

### Ring-ID

No trained watermark checkpoint is required. The adapter creates the heterogeneous channel 0 / ring channel 3 bank, applies real-projection correction and time shift, then saves the entire bank and selected index.

Verification compares the known key only. Identification searches **all saved candidates** before comparing the predicted index with the expected index. A bank of 2,048 uses upstream's full-bank order (`assigned_keys=-1` semantics); a smaller bank uses random sampling. Pattern indices are job-specific. Distance and nearest identity are not binary proof of watermark presence.

### WIND

Both native `WIND_full.py` and `WIND_fast.py` classes are used. Full mode retains the precomputed registry, group search, rotation search and sliding-window fallback. Its returned distance is the **first-stage** L2 distance even when fallback changes the predicted identity, matching the source's return value.

Fast mode saves only the noise registered by that generation job. Unlike an upstream multi-image run, the website does not yet maintain a shared multi-job fast registry. The result reports the actual registered count; do not treat a one-entry search as a large-population identification benchmark. Full mode is the appropriate website option for a populated registry. WIND's generation guidance remains its native fixed default 7.5.

### T2SMark

The SD 2.1 route encodes a random session key under a master key in one channel, and random message bits under the session key in the other three channels. It saves all three values privately. Decode first recovers the session key, then uses **that recovered key** to decode the message. Detect exposes the repository's L1 key statistic.

The separate upstream SD 3.5 path is **not implemented** in this adapter. User-authored messages and shared/fixed keys across multiple jobs are also not exposed; the website follows the random per-sample path.

### GaussMarker

Requires a matching 256-bit ChaCha watermark artifact and trained Gaussian Noise Restorer. Generate these together using the official workflow from its checkout:

```bash
python gaussmarker_gen.py --chacha --num 10 --output_path ./gen_10 --w1_path w1_256.pth
python train_GNR.py --train_steps 50000 --r 180 --s_min 1.0 --s_max 1.2 --fp 0.35 --neg_p 0.5 --model_nf 128 --batch_size 32 --num_workers 16 -ed 256bits --w_info_path w1_256.pth
```

Run those in the GaussMarker environment. They download models/data and perform substantial GPU work. Alternatively use compatible trusted pretrained artifacts. In the backend service environment:

```bash
export WATERMARK_GAUSSMARKER_W1=/absolute/path/to/w1_256.pth
export WATERMARK_GAUSSMARKER_GNR=/absolute/path/to/model_final.pth
```

The GNR must be trained for that W1, model width and input type. The adapter saves W1 and the Fourier pattern with the job and fingerprints the GNR. It performs spatial recovery, GNR restoration, Fourier comparison and the published `sd21_cls2.pkl` ensemble. Optional affine alignment and other upstream attack/evaluation branches are not web-integrated. The ensemble probability needs separate calibration, especially when parameters differ from its training settings.

### SEAL

No local watermark checkpoint is required, but model access/cache is required for `Salesforce/blip2-flan-t5-xl` and `kasraarabi/finetuned-caption-embedding`, in addition to SD 2.1.

Generation first renders a preliminary image, captions/embeds it, derives the semantic noise with seed 42, then renders the watermarked image. Verification re-captions the **analyzed image** and compares reconstructed noise patch distances. It does not substitute the saved original caption. The source's patch distances are returned; no arbitrary threshold is applied.

### ROBIN

Create clean reference images and optimize a watermark/hiding prompt using the repository:

```bash
python gen_clean_image.py --start 0 --end 200 --model_id /absolute/path/to/sd21 --save_path /absolute/path/to/clean-images
python gen_watermark.py --run_name no_attack --w_channel 3 --w_pattern ring --model_id /absolute/path/to/sd21 --data_root /absolute/path/to/clean-images
```

Inspect the upstream scripts' output directories and optimization settings before launching a long job. Then set:

```bash
export WATERMARK_ROBIN_CHECKPOINT=/absolute/path/to/optimized-watermark.pth
```

The file must contain `opt_wm` and `opt_acond`. Match model, 50-step schedule, channel 3, radii 5/30 and step 35 to the artifact you optimized, or configure compatible parameters. The adapter saves both tensors and verifies at the **intermediate** inversion state. Web-based optimization is not implemented.

### TAG-WM

Choose `trainable` to use the official DVRD checkpoint, downloaded from the trusted link in the pinned upstream README:

```bash
export WATERMARK_TAG_WM_DVRD=/absolute/path/to/DVRD-checkpoint.pth
```

Choose `trainfree` explicitly to use upstream's checkpoint-free refinement. Missing trainable weights never silently switch to trainfree. The adapter performs dual-mark embedding, inversion, refinement, tamper-aware message recovery, native bit-accuracy thresholds and tamper-mask export. It fingerprints the trainable checkpoint.

The wrapper currently uses upstream default shuffle/encryption seeds, FPR 1e-6, population 1,000,000 and 512px SD2 input. These are research defaults, not production-secret provisioning. Upload edited images against a linked generation job to inspect localization; IoU/Dice require a ground-truth mask and are not fabricated by the website.

### SERUM

Prepare the dataset and train the detector for the saved watermark grid through
the official commands. In the pinned source, `_prepare_optimizer` includes only
`score_model.parameters()`; despite the grid being stored as an `nn.Parameter`,
this training loop does not jointly optimize it:

```bash
python -m src.data.dataset --config config.yaml --mode generate --batch-size 16
python -m src.data.dataset --config config.yaml --mode augment
python -m src.training.train --config config.yaml
```

Then configure the matched artifacts:

```bash
export WATERMARK_SERUM_CONFIG=/absolute/path/to/config.yaml
export WATERMARK_SERUM_WATERMARK=/absolute/path/to/watermark.pt
export WATERMARK_SERUM_DETECTOR=/absolute/path/to/score_model.pt
```

The adapter supports the published 4x64x64 latent CNN and 512px images. It snapshots the config and detector with each job. Generation uses the native watermark/noise mixture; analysis uses native VAE encoding and the trained latent CNN. There is no diffusion inversion. Do not assume sigmoid 0.5 is a calibrated operating threshold.

## 4. Audit and start

```bash
python3 backend/integrations/repository_methods/setup_repositories.py --method tree-ring --check
python3 backend/integrations/repository_methods/setup_repositories.py --method ring-id --check
python3 backend/integrations/repository_methods/setup_repositories.py --method wind --check
python3 backend/integrations/repository_methods/setup_repositories.py --method t2smark --check
python3 backend/server.py --host 127.0.0.1 --port 8000
```

Use `--method all --check` after configuring all nine environments. The check verifies source revision, CUDA availability, imports and configured artifact paths; it **does not download weights or prove inference works**.

In another terminal, from `watermark-lab/`, run `npm install` and `npm run dev -- --host 127.0.0.1`. Use your existing production service/reverse-proxy procedure for deployment. Keep the backend private or behind authenticated access: the existing API has no user authentication, job listing exposes experiment metadata, and jobs can use significant GPU resources.

## 5. GPU acceptance checklist

1. Use the default model and a reproducible prompt/seed. Generate one image; confirm a completed result, real image and saved history entry.
2. Analyze that image using its linked job. Check every available action separately (Ring-ID verify/identify; T2SMark detect/decode; TAG-WM localize/decode).
3. Restart the backend and analyze the saved job again. Confirm its model, key bank, options and checkpoint binding are reused, even if current defaults differ.
4. Upload an edited copy while retaining the linked job; confirm it analyzes the upload, not the original. For TAG-WM inspect the separate mask.
5. Test an unrelated image. Distances/bit accuracy should change; do not report FPR, TPR or AUROC from one image.
6. Compare against the same pinned upstream workflow with the same model, parameters, state, precision and scheduler. Key artifacts from the website are in private state; their dictionaries are method-specific in the runner source.
7. Run held-out clean/watermarked/attacked batches offline for threshold calibration, false-positive estimates and paper metrics. Follow upstream dataset/attack commands for these. This is required before claiming reproduction or production accuracy.
8. Record GPU, driver, Python, package versions, model/checkpoint hashes and results before removing the experimental label.

## Development checks

```bash
python3 -m unittest discover -s backend/tests -v
python3 backend/tests/upstream_math_smoke.py
npm --prefix watermark-lab run build
npm --prefix watermark-lab run lint
```

The browser smoke test is `node watermark-lab/tests/repository-ui-smoke.cjs` with the frontend running. Install Playwright in your test environment, or set `PLAYWRIGHT_MODULE_PATH` to an existing installation. Optionally set `CHROME_EXECUTABLE` and `UI_URL`. It mocks API responses and checks all method/variant/action mappings, saved-job links, results, setup errors and responsive layouts; it does not run GPU inference.

The optional math smoke requires torch/torchvision/scipy and the reviewed sources (or configured source overrides). It uses a stand-in image pipeline to exercise native key/pattern math, **not a real diffusion model**.

## Private state and operational limits

Generated `private.pt` files contain keys, pattern banks or detector state. They are written with owner-only permissions and are not downloadable through `/files/`. Only load trusted operator-provided checkpoints: PyTorch/joblib artifacts can execute code during deserialization. Never accept checkpoint uploads from untrusted users.

Maintain backups of `backend/storage/outputs/`; deleting private state makes linked analysis impossible. Expect per-job disk growth, particularly for WIND. These adapters are synchronous and reload models per run, like the existing integrations. Run one GPU job at a time until a resource-aware queue is added. A two-hour process timeout is retained from the existing runner.
