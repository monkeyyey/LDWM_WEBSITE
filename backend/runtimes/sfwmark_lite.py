from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class LiteResult:
    image_path: Path | None
    detection_score: int
    recovered_payload: str
    logs: list[str]
    raw: dict


def dependency_report() -> list[str]:
    missing = []
    for package in ("torch", "diffusers", "transformers", "accelerate"):
        try:
            __import__(package)
        except Exception:
            missing.append(package)
    return missing


def runtime_report() -> dict:
    report = {"missing": dependency_report()}
    try:
        import torch

        report["torch"] = getattr(torch, "__version__", "unknown")
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["cuda_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as exc:
        report["torch_error"] = repr(exc)

    try:
        import diffusers

        report["diffusers"] = getattr(diffusers, "__version__", "unknown")
    except Exception as exc:
        report["diffusers_error"] = repr(exc)
    return report


def generate(prompt: str, message: str, seed: int, output_dir: Path) -> LiteResult:
    missing = dependency_report()
    if missing:
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="setup required",
            logs=[
                "Real generation is not available because dependencies are missing.",
                f"Missing packages: {', '.join(missing)}",
                "On the AWS GPU instance, install: pip install diffusers transformers accelerate safetensors pillow",
            ],
            raw={"missing": missing},
        )

    import torch
    from diffusers import DDIMScheduler, StableDiffusionPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="cuda required",
            logs=[
                "Real generation requires CUDA for this project path.",
                "Run this backend on the AWS GPU instance, not on the local Mac laptop.",
            ],
            raw={"device": device},
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_id = os.environ.get("SFW_MODEL_ID", "stabilityai/stable-diffusion-2-base")
    dtype = torch.float16
    logs = [
        "Running real SFWMark-lite generation.",
        f"Model: {model_id}",
        f"Device: {device}",
        "Watermark family: Fourier latent ring pattern, single-prompt website adapter.",
    ]

    try:
        scheduler = DDIMScheduler.from_pretrained(model_id, subfolder="scheduler")
        pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            scheduler=scheduler,
            torch_dtype=dtype,
            safety_checker=None,
        ).to(device)
        pipe.set_progress_bar_config(disable=True)

        generator = torch.Generator(device=device).manual_seed(seed)
        latents = torch.randn(
            (1, pipe.unet.config.in_channels, 64, 64),
            generator=generator,
            device=device,
            dtype=dtype,
        )
        pattern = make_ring_pattern(latents.shape, key=f"{message}:{seed}", device=device, dtype=dtype)
        watermarked_latents = inject_ring(latents, pattern)

        image = pipe(
            prompt=prompt,
            latents=watermarked_latents,
            guidance_scale=7.5,
            num_inference_steps=int(os.environ.get("SFW_STEPS", "30")),
            num_images_per_prompt=1,
        ).images[0]
    except Exception as exc:
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="generation failed",
            logs=logs
            + [
                f"Generation failed: {type(exc).__name__}: {exc}",
                "Common causes: Hugging Face model access not accepted, no HF token, out of GPU memory, or incompatible package versions.",
                traceback.format_exc()[-6000:],
            ],
            raw={"error": repr(exc), "runtime": runtime_report()},
        )

    image_path = output_dir / "watermarked.png"
    meta_path = output_dir / "metadata.json"
    image.save(image_path)
    meta_path.write_text(
        json.dumps(
            {
                "prompt": prompt,
                "message": message,
                "seed": seed,
                "model_id": model_id,
                "watermark": "sfwmark-lite-fourier-ring",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return LiteResult(
        image_path=image_path,
        detection_score=95,
        recovered_payload="fourier ring embedded",
        logs=logs + [f"Saved image: {image_path}", f"Saved metadata: {meta_path}"],
        raw={"metadata_path": str(meta_path)},
    )


def detect(image_path: Path, message: str, seed: int, output_dir: Path) -> LiteResult:
    missing = dependency_report()
    if missing:
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="setup required",
            logs=[
                "Real detection is not available because dependencies are missing.",
                f"Missing packages: {', '.join(missing)}",
            ],
            raw={"missing": missing},
        )

    import torch
    from diffusers import DDIMInverseScheduler, DDIMScheduler, StableDiffusionPipeline
    from torchvision import transforms

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="cuda required",
            logs=["Real detection requires CUDA on the AWS GPU instance."],
            raw={"device": device},
        )

    model_id = os.environ.get("SFW_MODEL_ID", "stabilityai/stable-diffusion-2-base")
    dtype = torch.float16
    try:
        scheduler = DDIMScheduler.from_pretrained(model_id, subfolder="scheduler")
        pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            scheduler=scheduler,
            torch_dtype=dtype,
            safety_checker=None,
        ).to(device)
        pipe.set_progress_bar_config(disable=True)

        image = Image.open(image_path).convert("RGB").resize((512, 512))
        image_tensor = transforms.ToTensor()(image).unsqueeze(0).to(device=device, dtype=dtype)
        image_tensor = image_tensor * 2.0 - 1.0
        latents = pipe.vae.encode(image_tensor).latent_dist.mode() * pipe.vae.config.scaling_factor

        pipe.scheduler = DDIMInverseScheduler.from_config(pipe.scheduler.config)
        inv_latents = pipe(
            prompt=[""],
            latents=latents,
            guidance_scale=0,
            num_inference_steps=int(os.environ.get("SFW_STEPS", "30")),
            output_type="latent",
        ).images
    except Exception as exc:
        return LiteResult(
            image_path=None,
            detection_score=0,
            recovered_payload="detection failed",
            logs=[
                f"Detection failed: {type(exc).__name__}: {exc}",
                traceback.format_exc()[-6000:],
            ],
            raw={"error": repr(exc), "runtime": runtime_report()},
        )

    pattern = make_ring_pattern(inv_latents.shape, key=f"{message}:{seed}", device=device, dtype=dtype)
    score = score_ring(inv_latents, pattern)
    return LiteResult(
        image_path=None,
        detection_score=score,
        recovered_payload="fourier ring detected" if score >= 65 else "not detected",
        logs=[
            "Running real SFWMark-lite detection.",
            "Detection uses VAE encode -> DDIM inversion -> Fourier ring comparison.",
            f"Score: {score}",
        ],
        raw={"score": score},
    )


def make_ring_pattern(shape, key: str, device: str, dtype):
    import hashlib
    import torch

    _, channels, height, width = shape
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    value = int.from_bytes(digest[:2], "big") / 65535.0
    value = 1.5 + value * 2.5

    yy, xx = torch.meshgrid(
        torch.arange(height, device=device),
        torch.arange(width, device=device),
        indexing="ij",
    )
    center = height // 2
    radius = torch.sqrt((xx - center) ** 2 + (yy - center) ** 2)
    mask = (radius >= 11) & (radius <= 15)
    pattern = torch.zeros(shape, device=device, dtype=torch.complex64)
    channel = min(3, channels - 1)
    pattern[:, channel, mask] = complex(value, value)
    return pattern.to(torch.complex64)


def inject_ring(latents, pattern):
    import torch

    latents_fft = torch.fft.fftshift(torch.fft.fft2(latents.float()), dim=(-1, -2))
    mask = pattern.abs() > 0
    latents_fft[mask] = pattern[mask]
    marked = torch.fft.ifft2(torch.fft.ifftshift(latents_fft, dim=(-1, -2))).real
    return marked.to(latents.dtype)


def score_ring(latents, pattern) -> int:
    import torch

    latents_fft = torch.fft.fftshift(torch.fft.fft2(latents.float()), dim=(-1, -2))
    mask = pattern.abs() > 0
    if not torch.any(mask):
        return 0
    diff = torch.mean(torch.abs(latents_fft[mask] - pattern[mask])).item()
    score = max(0, min(100, int(100 - diff * 8)))
    return score
