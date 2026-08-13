from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))

    try:
        import torch
        from PIL import Image
        from diffusers import DDIMInverseScheduler, DDIMScheduler, StableDiffusionPipeline
        from ldpc import gauss_decode, gauss_encode, latentsToWatermark, ldpc_decode, ldpc_encode, watermarkToLatents

        device = choose_device(torch)
        # The upstream Gaussian-Shannon generation path uses float32. Keeping
        # that dtype avoids changing the latent symbols during integration.
        dtype = torch.float32
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)

        if args.operation == "generate":
            result = generate(args, torch, Image, DDIMScheduler, StableDiffusionPipeline, gauss_encode, ldpc_encode, watermarkToLatents, device, dtype)
        else:
            result = extract(args, torch, Image, DDIMInverseScheduler, StableDiffusionPipeline, gauss_decode, ldpc_decode, latentsToWatermark, device, dtype)
    except Exception as exc:
        result = {
            "status": "failed",
            "recovered_payload": f"{type(exc).__name__}: {exc}",
            "detection_score": 0,
            "raw": {"error": repr(exc)},
        }
    print("@@RESULT@@" + json.dumps(result))
    return 0 if result.get("status") == "completed" else 1


def generate(args, torch, Image, DDIMScheduler, StableDiffusionPipeline, gauss_encode, ldpc_encode, watermarkToLatents, device, dtype):
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bits = parse_bits(args.message)
    batch_size = 1
    if args.coding == "gaussian":
        redundancy = effective_redundancy(args)
        wm = gauss_encode(bits, batch_size=batch_size, redundancy=redundancy)
        state = {"coding": "gaussian", "redundancy": redundancy, "num_elements": int(wm.shape[1])}
    else:
        redundancy = effective_redundancy(args)
        wm, H, G = ldpc_encode(bits, batch_size=batch_size, redundancy=redundancy, CR=0.25)
        state = {"coding": "ldpc", "redundancy": redundancy, "num_elements": int(wm.shape[1]), "message": bits.tolist()}
        from scipy import sparse

        # pyldpc may return H as a dense ndarray even when sparse=True.
        # save_npz requires an actual SciPy sparse matrix, while extraction
        # can load the same matrix without changing the upstream algorithm.
        sparse.save_npz(output / "ldpc_H.npz", sparse.csr_matrix(H))
        np.save(output / "ldpc_G.npy", G)

    model_id = args.model_id
    scheduler = DDIMScheduler.from_pretrained(model_id, subfolder="scheduler")
    pipe = StableDiffusionPipeline.from_pretrained(model_id, scheduler=scheduler, safety_checker=None, torch_dtype=dtype).to(device)
    pipe.set_progress_bar_config(disable=True)
    latents = torch.randn((1, 4, 64, 64), device=device, dtype=dtype)
    latents = watermarkToLatents(wm.to(device=device, dtype=dtype), latents)
    result = pipe(prompt=[args.prompt], negative_prompt=[""], guidance_scale=7.5, num_inference_steps=args.steps, latents=latents, output_type="pil")
    image_path = output / "watermarked.png"
    result.images[0].save(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Gaussian-Shannon did not produce {image_path}")
    state.update({"message": bits.tolist(), "model_id": model_id, "prompt": args.prompt, "seed": args.seed, "steps": args.steps})
    (output / "metadata.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"status": "completed", "detection_score": 0, "recovered_payload": bits_to_string(bits), "image_path": str(image_path), "raw": state}


def extract(args, torch, Image, DDIMInverseScheduler, StableDiffusionPipeline, gauss_decode, ldpc_decode, latentsToWatermark, device, dtype):
    if not args.image:
        raise ValueError("Gaussian-Shannon extraction requires an image")
    image_path = Path(args.image).resolve()
    state_dir = Path(args.state_dir).resolve() if args.state_dir else None
    state = read_state(state_dir)
    coding = args.coding or state.get("coding", "gaussian")
    redundancy = int(args.redundancy or state.get("redundancy", 64 if coding == "gaussian" else 16))
    num_elements = int(state.get("num_elements", 256 * redundancy if coding == "gaussian" else 1024 * redundancy))
    expected = np.array(parse_bits(args.message), dtype=int)

    image = Image.open(image_path).convert("RGB")
    image = image.resize((512, 512))
    pixels = torch.from_numpy(np.asarray(image).astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to(device=device, dtype=dtype)
    pixels = pixels * 2.0 - 1.0
    model_id = str(state.get("model_id", args.model_id))
    pipe = StableDiffusionPipeline.from_pretrained(model_id, scheduler=DDIMInverseScheduler.from_pretrained(model_id, subfolder="scheduler"), safety_checker=None, torch_dtype=dtype).to(device)
    pipe.set_progress_bar_config(disable=True)
    latents = pipe.vae.encode(pixels).latent_dist.mean * 0.18215
    inv_latents, _ = pipe(prompt=["man"], negative_prompt=[""], guidance_scale=1.0, width=512, height=512, num_inference_steps=args.steps, latents=latents, output_type="latent", return_dict=False)
    final_tensor = latentsToWatermark(num_elements, inv_latents)

    if coding == "gaussian":
        decoded = gauss_decode(final_tensor, redundancy)[0]
    else:
        if state_dir is None or not (state_dir / "ldpc_H.npz").is_file() or not (state_dir / "ldpc_G.npy").is_file():
            raise RuntimeError("LDPC extraction needs the generation job state containing H and G")
        from scipy import sparse

        H = sparse.load_npz(state_dir / "ldpc_H.npz")
        G = np.load(state_dir / "ldpc_G.npy", allow_pickle=False)
        decoded, _ = ldpc_decode(final_tensor, H, G, redundancy, table_decision=True, snr=0)
        decoded = decoded[0]
    decoded = np.asarray(decoded, dtype=int)[:256]
    bit_string = bits_to_string(decoded)
    bit_error_rate = float(np.mean(decoded != expected)) if expected.shape == decoded.shape else None
    return {
        "status": "completed",
        "detection_score": int(round((1.0 - (bit_error_rate or 0.0)) * 100)),
        "recovered_payload": bit_string,
        "raw": {
            "coding": coding,
            "redundancy": redundancy,
            "num_elements": num_elements,
            "latent_shape": [1, 4, 64, 64],
            "decoder": "majority vote",
            "bit_error_rate": bit_error_rate,
        },
    }


def choose_device(torch):
    requested = os.environ.get("WATERMARK_DEVICE")
    if requested:
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def parse_bits(value: str) -> np.ndarray:
    if value in {"", "256-bit zero message"}:
        return np.zeros(256, dtype=int)
    bits = value.replace(" ", "")
    if len(bits) != 256 or any(bit not in "01" for bit in bits):
        raise ValueError("Gaussian-Shannon messages must contain exactly 256 binary bits")
    return np.array([int(bit) for bit in bits], dtype=int)


def bits_to_string(bits) -> str:
    return "".join(str(int(bit)) for bit in bits)


def read_state(state_dir: Path | None) -> dict:
    if state_dir is None or not (state_dir / "metadata.json").is_file():
        return {}
    return json.loads((state_dir / "metadata.json").read_text(encoding="utf-8"))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=["generate", "extract"], required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--state-dir")
    parser.add_argument("--image")
    parser.add_argument("--coding", choices=["gaussian", "ldpc"], default="gaussian")
    parser.add_argument("--message", default="256-bit zero message")
    parser.add_argument("--prompt", default="a clean product photo of a ceramic mug on a desk")
    parser.add_argument(
        "--model-id",
        default=os.environ.get("WATERMARK_GS_MODEL_ID", "sd2-community/stable-diffusion-2-1-base"),
    )
    parser.add_argument("--redundancy", type=int)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def effective_redundancy(args) -> int:
    if args.redundancy is not None:
        return args.redundancy
    return 64 if args.coding == "gaussian" else 16


if __name__ == "__main__":
    raise SystemExit(main())
