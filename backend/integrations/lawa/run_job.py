from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    try:
        if args.operation in {"generate", "quality"}:
            result = generate(args, repo)
        else:
            result = extract(args, repo)
    except Exception as exc:
        result = {"status": "failed", "recovered_payload": f"{type(exc).__name__}: {exc}", "detection_score": 0, "raw": {"error": repr(exc)}}
    print("@@RESULT@@" + json.dumps(result))
    return 0 if result.get("status") == "completed" else 1


def generate(args, repo: Path):
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    native_out = output / "native"
    native_out.mkdir(parents=True, exist_ok=True)
    command = [
        os.environ.get("WATERMARK_LAWA_PYTHON", sys.executable),
        str(repo / "inference_AIGC.py"),
        "--config", args.config,
        "--weight", args.weight,
        "--ckpt", args.ckpt,
        "--message", args.message,
        "--message_len", "48",
        "--prompt", args.prompt,
        "--outdir", str(native_out),
        "--n_samples", "1",
        "--n_iter", "1",
        "--seed", str(args.seed),
        "--skip_grid",
    ]
    completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, timeout=7200)
    if completed.stdout:
        print(completed.stdout[-12000:])
    if completed.stderr:
        print(completed.stderr[-12000:], file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"LaWa inference_AIGC.py exited with {completed.returncode}")
    candidates = sorted(native_out.rglob("*_watermarked.png"))
    if not candidates:
        raise FileNotFoundError(f"LaWa did not produce a *_watermarked.png file under {native_out}")
    image_path = output / "watermarked.png"
    shutil.copy2(candidates[0], image_path)
    metadata = {"message": args.message, "prompt": args.prompt, "seed": args.seed, "config": args.config, "weight": args.weight, "ckpt": args.ckpt}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    bit_accuracy = parse_last_metric(completed.stdout, "Bit acc")
    metadata["bit_accuracy"] = bit_accuracy
    return {"status": "completed", "detection_score": int(round((bit_accuracy or 0.0) * 100)), "recovered_payload": args.message, "image_path": str(image_path), "raw": metadata}


def extract(args, repo: Path):
    import numpy as np
    import torch
    from PIL import Image, ImageEnhance, ImageFilter
    from omegaconf import OmegaConf

    sys.path.insert(0, str(repo / "stable-diffusion"))
    sys.path.insert(0, str(repo))
    from ldm.util import instantiate_from_config

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config = normalize_targets(OmegaConf.to_container(OmegaConf.load(args.config).model, resolve=False))
    model = instantiate_from_config(config)
    state_dict = torch.load(args.weight, map_location="cpu")
    if "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device).eval()
    for parameter in model.parameters():
        parameter.requires_grad = False

    image = Image.open(args.image).convert("RGB")
    image = apply_attack(image, args.attack, ImageEnhance, ImageFilter)
    image = image.resize((512, 512))
    tensor = torch.from_numpy(np.asarray(image).astype(np.float32) / 127.5 - 1.0).permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model.decoder(tensor)
    decoded = (logits[0] > 0).to(torch.int).detach().cpu().numpy().tolist()
    bits = "".join(str(bit) for bit in decoded[:48])
    expected = args.message if len(args.message) == 48 and set(args.message) <= {"0", "1"} else None
    bit_error_rate = sum(left != right for left, right in zip(bits, expected)) / 48 if expected else None
    accuracy = 1.0 - bit_error_rate if bit_error_rate is not None else None
    return {"status": "completed", "detection_score": int(round((accuracy or 0.0) * 100)), "recovered_payload": bits, "raw": {"bit_error_rate": bit_error_rate, "bit_accuracy": accuracy, "attack": args.attack}}


def apply_attack(image, attack, ImageEnhance, ImageFilter):
    if not attack or attack == "None":
        return image
    normalized = attack.lower()
    if "jpeg" in normalized:
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=60)
        buffer.seek(0)
        from PIL import Image

        return Image.open(buffer).convert("RGB")
    if "rotation" in normalized:
        from PIL import Image

        return image.rotate(10, resample=Image.Resampling.BILINEAR)
    if "crop" in normalized:
        width, height = image.size
        return image.crop((width // 10, height // 10, width * 9 // 10, height * 9 // 10)).resize((width, height))
    if "resize" in normalized:
        width, height = image.size
        return image.resize((width // 2, height // 2)).resize((width, height))
    if "blur" in normalized:
        return image.filter(ImageFilter.GaussianBlur(radius=1.5))
    if "contrast" in normalized:
        return ImageEnhance.Contrast(image).enhance(0.8)
    if "brightness" in normalized:
        return ImageEnhance.Brightness(image).enhance(0.8)
    return image


def parse_last_metric(output: str, label: str) -> float | None:
    matches = re.findall(rf"{re.escape(label)}:\s*([0-9.]+)", output)
    return float(matches[-1]) if matches else None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=["generate", "extract", "quality"], required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--image")
    parser.add_argument("--message", default="110111001110110001000000011101000110011100110101")
    parser.add_argument("--prompt", default="A white plate of food on a dining table")
    parser.add_argument("--config", default="configs/SD14_LaWa_inference.yaml")
    parser.add_argument("--weight", default="weights/LaWa/last.ckpt")
    parser.add_argument("--ckpt", default="weights/stable-diffusion-v1/model.ckpt")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--attack", default="None")
    return parser.parse_args()


def normalize_targets(value):
    if isinstance(value, dict):
        return {key: normalize_targets(normalize_target(key, item)) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_targets(item) for item in value]
    return value


def normalize_target(key, value):
    if key == "target" and isinstance(value, str) and value.startswith("stable-diffusion."):
        return value.removeprefix("stable-diffusion.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
