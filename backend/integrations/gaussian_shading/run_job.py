from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))

    try:
        import numpy as np
        import torch
        from PIL import Image
        from diffusers import DPMSolverMultistepScheduler
        from image_utils import set_random_seed, transform_img
        from inverse_stable_diffusion import InversableStableDiffusionPipeline
        from watermark import Gaussian_Shading, Gaussian_Shading_chacha

        if not torch.cuda.is_available():
            raise RuntimeError("Gaussian Shading's released implementation requires CUDA")
        set_random_seed(args.seed)
        np.random.seed(args.seed)
        if args.operation == "generate":
            result = generate(args, torch, DPMSolverMultistepScheduler, InversableStableDiffusionPipeline, Gaussian_Shading, Gaussian_Shading_chacha)
        else:
            result = verify(args, torch, Image, DPMSolverMultistepScheduler, InversableStableDiffusionPipeline, Gaussian_Shading, Gaussian_Shading_chacha, transform_img)
    except Exception as exc:
        result = {
            "status": "failed",
            "recovered_payload": f"{type(exc).__name__}: {exc}",
            "detection_score": 0,
            "raw": {"error": repr(exc)},
        }

    print("@@RESULT@@" + json.dumps(result))
    return 0 if result.get("status") == "completed" else 1


def generate(args, torch, Scheduler, Pipeline, SimpleWatermark, ChachaWatermark):
    validate_factors(args.channel_copy, args.hw_copy)
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    watermark = make_watermark(args.variant, args.channel_copy, args.hw_copy, args.fpr, args.user_number, SimpleWatermark, ChachaWatermark)
    if watermark.tau_onebit is None or watermark.tau_bits is None:
        raise ValueError("The copy factors, FPR, and user population do not produce valid repository thresholds")
    initial_latents = watermark.create_watermark_and_return_w()

    pipe = load_pipeline(args.model_id, torch, Scheduler, Pipeline)
    generated = pipe(
        args.prompt,
        num_images_per_prompt=1,
        guidance_scale=7.5,
        num_inference_steps=args.steps,
        height=512,
        width=512,
        latents=initial_latents,
    )
    image_path = output / "watermarked.png"
    generated.images[0].save(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Gaussian Shading did not produce {image_path}")

    torch.save(watermark.watermark.detach().cpu(), output / "watermark.pt")
    if args.variant == "chacha":
        (output / "chacha_key.bin").write_bytes(watermark.key)
        (output / "chacha_nonce.bin").write_bytes(watermark.nonce)
    else:
        torch.save(watermark.key.detach().cpu(), output / "xor_key.pt")

    message = bits_to_string(watermark.watermark)
    metadata = {
        "method": "gaussian-shading",
        "submethod_id": args.variant,
        "gaussian_shading_variant": args.variant,
        "message": message,
        "prompt": args.prompt,
        "seed": args.seed,
        "model_id": args.model_id,
        "inference_steps": args.steps,
        "channel_copy": args.channel_copy,
        "hw_copy": args.hw_copy,
        "fpr": args.fpr,
        "user_number": args.user_number,
        "mark_length": int(watermark.marklength),
        "tau_detection": watermark.tau_onebit,
        "tau_traceability": watermark.tau_bits,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "status": "completed",
        "detection_score": 0,
        "recovered_payload": message,
        "image_path": str(image_path),
        "raw": metadata,
    }


def verify(args, torch, Image, Scheduler, Pipeline, SimpleWatermark, ChachaWatermark, transform_img):
    if not args.image or not args.state_dir:
        raise ValueError("Gaussian Shading verification requires an image and generation state")
    state_dir = Path(args.state_dir).resolve()
    metadata = read_metadata(state_dir)
    if metadata.get("method") != "gaussian-shading":
        raise ValueError("The selected source job is not a Gaussian Shading generation")
    if metadata.get("gaussian_shading_variant") != args.variant:
        raise ValueError("The selected source job uses a different Gaussian Shading variant")

    variant = str(metadata["gaussian_shading_variant"])
    watermark = make_watermark(
        variant,
        int(metadata["channel_copy"]),
        int(metadata["hw_copy"]),
        float(metadata["fpr"]),
        int(metadata["user_number"]),
        SimpleWatermark,
        ChachaWatermark,
    )
    watermark.watermark = torch.load(state_dir / "watermark.pt", map_location="cpu").cuda()
    if variant == "chacha":
        watermark.key = (state_dir / "chacha_key.bin").read_bytes()
        watermark.nonce = (state_dir / "chacha_nonce.bin").read_bytes()
    else:
        watermark.key = torch.load(state_dir / "xor_key.pt", map_location="cpu").cuda()

    pipe = load_pipeline(str(metadata["model_id"]), torch, Scheduler, Pipeline)
    text_embeddings = pipe.get_text_embedding("")
    image = Image.open(args.image).convert("RGB")
    image_tensor = transform_img(image).unsqueeze(0).to(text_embeddings.dtype).cuda()
    image_latents = pipe.get_image_latents(image_tensor, sample=False)
    reversed_latents = pipe.forward_diffusion(
        latents=image_latents,
        text_embeddings=text_embeddings,
        guidance_scale=1,
        num_inference_steps=int(metadata["inference_steps"]),
    )

    recovered = recover_watermark(variant, watermark, reversed_latents, torch)
    accuracy = float((recovered == watermark.watermark).float().mean().item())
    bit_error_rate = 1.0 - accuracy
    detected = accuracy >= float(watermark.tau_onebit)
    traceable = accuracy >= float(watermark.tau_bits)
    recovered_bits = bits_to_string(recovered)
    return {
        "status": "completed",
        "detection_score": int(round(accuracy * 100)),
        "recovered_payload": recovered_bits,
        "raw": {
            "gaussian_shading_variant": variant,
            "bit_accuracy": accuracy,
            "bit_error_rate": bit_error_rate,
            "detected": detected,
            "traceable": traceable,
            "tau_detection": watermark.tau_onebit,
            "tau_traceability": watermark.tau_bits,
            "fpr": metadata["fpr"],
            "user_number": metadata["user_number"],
            "channel_copy": metadata["channel_copy"],
            "hw_copy": metadata["hw_copy"],
            "mark_length": metadata["mark_length"],
            "latent_shape": [1, 4, 64, 64],
            "inversion_prompt": "",
        },
    }


def load_pipeline(model_id, torch, Scheduler, Pipeline):
    scheduler = Scheduler.from_pretrained(model_id, subfolder="scheduler")
    pipe = Pipeline.from_pretrained(model_id, scheduler=scheduler, torch_dtype=torch.float16)
    pipe.safety_checker = None
    pipe.set_progress_bar_config(disable=True)
    return pipe.to("cuda")


def make_watermark(variant, channel_copy, hw_copy, fpr, user_number, SimpleWatermark, ChachaWatermark):
    watermark_class = ChachaWatermark if variant == "chacha" else SimpleWatermark
    return watermark_class(channel_copy, hw_copy, fpr, user_number)


def recover_watermark(variant, watermark, reversed_latents, torch):
    reversed_message = (reversed_latents > 0).int()
    if variant == "chacha":
        decrypted = watermark.stream_key_decrypt(reversed_message.flatten().cpu().numpy())
    else:
        decrypted = (reversed_message + watermark.key) % 2
    return watermark.diffusion_inverse(decrypted).to(torch.uint8)


def bits_to_string(bits) -> str:
    return "".join(str(int(bit)) for bit in bits.detach().cpu().reshape(-1).tolist())


def read_metadata(state_dir: Path) -> dict:
    path = state_dir / "metadata.json"
    if not path.is_file():
        raise FileNotFoundError("Gaussian Shading generation metadata is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_factors(channel_copy: int, hw_copy: int) -> None:
    if channel_copy not in {1, 2, 4}:
        raise ValueError("channel_copy must be one of 1, 2, or 4")
    if hw_copy not in {1, 2, 4, 8, 16, 32, 64}:
        raise ValueError("hw_copy must divide the 64 x 64 latent dimensions")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--operation", choices=["generate", "verify"], required=True)
    parser.add_argument("--variant", choices=["simple", "chacha"], default="chacha")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-dir")
    parser.add_argument("--image")
    parser.add_argument("--prompt", default="a clean product photo of a ceramic mug on a desk")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--channel-copy", type=int, default=1)
    parser.add_argument("--hw-copy", type=int, default=8)
    parser.add_argument("--fpr", type=float, default=0.000001)
    parser.add_argument("--user-number", type=int, default=1000000)
    parser.add_argument("--model-id", default=os.environ.get("WATERMARK_GSHADING_MODEL_ID", "sd2-community/stable-diffusion-2-1-base"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
