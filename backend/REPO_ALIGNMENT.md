# Repository Alignment Notes

This file records what the current website/backend assumes about the three first-pass model integrations.

## SFWMark

Repo: `work/repos/SFWMark`

Native behavior:

- Generation-time latent-noise watermarking.
- Detection through DDIM inversion and Fourier-domain analysis.
- Robustness evaluation with attacks including JPEG, Diffusion, center crop (`CC`), random crop (`RC`), blur, noise, brightness, and contrast.

Important repo config:

- `python src/generate.py --wm_type HSQR --dataset_id coco`
- `wm_type` options: `Tree-Ring`, `RingID`, `HSTR`, `HSQR`
- `dataset_id` options: `coco`, `Gustavo`, `DB1k`

Website alignment:

- Uses SFWMark as a Fourier latent watermark method.
- Exposes `wm_type` as the payload/config field.
- Does not claim arbitrary uploaded-image watermark embedding.

## Gaussian Shannon

Repo: `work/repos/Gaussian-Shannon`

Native behavior:

- Generation-time latent watermarking based on communication coding.
- DDIM inversion and decoding for detection.
- Robustness helpers for JPEG, blur, noise, crop, random drop, SDEdit, and adversarial embedding-space attack.

Important repo config:

- Default model: `stabilityai/stable-diffusion-2-1`
- Message length in code: `256` bits
- Common redundancy value: `64`
- Code is function-oriented in `infer.py` rather than a polished end-user CLI.

Website alignment:

- Uses Gaussian Shannon as the exact/recoverable bit-payload representative.
- Labels payload as a 256-bit mode, not arbitrary short text.
- Adapter should wrap `infer.py` functions or add a thin CLI before production use.

## LaWa

Repo: `work/repos/LaWa`

Native behavior:

- In-generation image watermarking with Stable Diffusion v1.4 and a modified decoder.
- Uses pretrained weights for a 48-bit binary watermark.
- Generates original, watermarked, difference image, quality CSV, and attack CSV.

Important repo config:

- `python inference_AIGC.py --config configs/SD14_LaWa_inference.yaml --message_len 48 --message <48 bits>`
- Modified decoder: `weights/LaWa/last.ckpt`
- First-stage autoencoder: `weights/first_stage_models/first_stage_KL-f8.ckpt`
- Stable Diffusion checkpoint: `weights/stable-diffusion-v1/model.ckpt`
- Default generation resolution: `512x512`
- Default sampling: `ddim_steps=50`

Website alignment:

- Uses LaWa as the VAE/decoder-integrated latent watermark representative.
- Enforces the concept of a 48-bit binary message in the UI text/default.
- Does not claim arbitrary uploaded-image watermark embedding.

## Key Product Constraint

For these three repos, the reliable first product workflow is:

```text
generate watermarked image -> optionally attack/edit -> detect/evaluate watermark
```

The workflow:

```text
upload arbitrary image -> embed watermark into that image
```

is not natively supported by all three selected repos and should not be presented as a guaranteed capability unless a custom post-hoc adapter is built.

## Confirmation Implementation Status

The backend adapters now expose a `command_plan()` for each method. In normal mode the server returns mock results plus the real command/function plan. If the correct repo environment, model weights, and GPU are available, setting:

```bash
WATERMARK_EXECUTE_REAL=1
```

before starting `backend/server.py` makes adapters attempt to execute their command plan.

This is intentionally off by default because these commands require repo-specific conda/Docker environments and large model checkpoints.

Current adapter readiness:

- `SFWMark`: has native `generate.py` and `detect.py`; easiest to make fully real first.
- `Gaussian Shannon`: has generation/detection functions in `infer.py`, but not a polished CLI; adapter calls Python functions through a small inline wrapper.
- `LaWa`: has generation plus immediate extraction/attack CSVs in `inference_AIGC.py`; standalone uploaded-image detection needs a small custom wrapper around `model.decoder(image_tensor)`.
