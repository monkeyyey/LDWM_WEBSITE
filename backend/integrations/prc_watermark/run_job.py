from __future__ import annotations

import argparse
import json
import os
import pickle
import random
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
        from inversion import exact_inversion, generate, stable_diffusion_pipe
        from src.prc import Decode, Detect, Encode, KeyGen
        import src.pseudogaussians as prc_gaussians

        if not torch.cuda.is_available():
            raise RuntimeError("PRC-Watermark's released implementation requires CUDA")
        seed_everything(args.seed, random, np, torch)
        if args.operation == "generate":
            result = generate_image(args, torch, KeyGen, Encode, prc_gaussians, stable_diffusion_pipe, generate)
        else:
            result = verify_image(args, torch, Image, Detect, Decode, prc_gaussians, stable_diffusion_pipe, exact_inversion)
    except Exception as exc:
        result = {
            "status": "failed",
            "recovered_payload": f"{type(exc).__name__}: {exc}",
            "detection_score": 0,
            "raw": {"error": repr(exc)},
        }

    print("@@RESULT@@" + json.dumps(result))
    return 0 if result.get("status") == "completed" else 1


def generate_image(args, torch, KeyGen, Encode, prc_gaussians, stable_diffusion_pipe, generate):
    if not 0 < args.fpr < 1:
        raise ValueError("PRC false-positive rate must be between 0 and 1")
    if args.prc_t < 2:
        raise ValueError("PRC parity-check sparsity t must be at least 2")

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    codeword_length = 4 * 64 * 64
    encoding_key, decoding_key = KeyGen(codeword_length, false_positive_rate=args.fpr, t=args.prc_t)
    with (output / "prc_keys.pkl").open("wb") as key_file:
        pickle.dump((encoding_key, decoding_key), key_file)

    codeword = Encode(encoding_key)
    initial_latents = prc_gaussians.sample(codeword).reshape(1, 4, 64, 64).cuda()
    pipe = stable_diffusion_pipe(solver_order=1, model_id=args.model_id, cache_dir=os.environ.get("HF_HOME"))
    pipe.set_progress_bar_config(disable=True)
    image, _, _ = generate(
        prompt=args.prompt,
        init_latents=initial_latents,
        num_inference_steps=args.steps,
        solver_order=1,
        pipe=pipe,
        gen_seed=args.seed,
    )
    image_path = output / "watermarked.png"
    image.save(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"PRC-Watermark did not produce {image_path}")

    metadata = {
        "method": "prc-watermark",
        "submethod_id": "prc",
        "message": "Keyed binary PRC watermark",
        "prompt": args.prompt,
        "seed": args.seed,
        "model_id": args.model_id,
        "inference_steps": args.steps,
        "fpr": args.fpr,
        "prc_t": args.prc_t,
        "posterior_variance": args.posterior_variance,
        "codeword_length": codeword_length,
        "solver_order": 1,
        "inversion_order": 0,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "status": "completed",
        "detection_score": 0,
        "recovered_payload": "Keyed binary PRC watermark",
        "image_path": str(image_path),
        "raw": metadata,
    }


def verify_image(args, torch, Image, Detect, Decode, prc_gaussians, stable_diffusion_pipe, exact_inversion):
    if not args.image or not args.state_dir:
        raise ValueError("PRC verification requires an image and generation state")
    state_dir = Path(args.state_dir).resolve()
    metadata = read_metadata(state_dir)
    if metadata.get("method") != "prc-watermark":
        raise ValueError("The selected source job is not a PRC-Watermark generation")
    key_path = state_dir / "prc_keys.pkl"
    if not key_path.is_file():
        raise FileNotFoundError("PRC decoding key is missing from the generation job")
    with key_path.open("rb") as key_file:
        _, decoding_key = pickle.load(key_file)

    pipe = stable_diffusion_pipe(solver_order=1, model_id=str(metadata["model_id"]), cache_dir=os.environ.get("HF_HOME"))
    pipe.set_progress_bar_config(disable=True)
    image = Image.open(args.image).convert("RGB")
    reversed_latents = exact_inversion(
        image,
        prompt="",
        test_num_inference_steps=int(metadata["inference_steps"]),
        inv_order=int(metadata["inversion_order"]),
        pipe=pipe,
    )
    posteriors = prc_gaussians.recover_posteriors(
        reversed_latents.to(torch.float64).flatten().cpu(),
        variances=float(metadata["posterior_variance"]),
    ).flatten().cpu()
    detection_result = bool(Detect(decoding_key, posteriors))
    decoded = Decode(decoding_key, posteriors)
    decoding_result = decoded is not None
    combined_result = detection_result or decoding_result
    return {
        "status": "completed",
        "detection_score": 100 if combined_result else 0,
        "recovered_payload": "watermark detected" if combined_result else "watermark not detected",
        "raw": {
            "detection_result": detection_result,
            "decoding_result": decoding_result,
            "combined_result": combined_result,
            "decision_rule": "Detect OR Decode",
            "fpr": metadata["fpr"],
            "prc_t": metadata["prc_t"],
            "posterior_variance": metadata["posterior_variance"],
            "codeword_length": metadata["codeword_length"],
            "latent_shape": [1, 4, 64, 64],
            "inversion_order": metadata["inversion_order"],
            "inversion_prompt": "",
        },
    }


def seed_everything(seed, random, np, torch):
    os.environ["PL_GLOBAL_SEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def read_metadata(state_dir: Path) -> dict:
    path = state_dir / "metadata.json"
    if not path.is_file():
        raise FileNotFoundError("PRC generation metadata is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--operation", choices=["generate", "verify"], required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-dir")
    parser.add_argument("--image")
    parser.add_argument("--prompt", default="a clean product photo of a ceramic mug on a desk")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--fpr", type=float, default=0.00001)
    parser.add_argument("--prc-t", type=int, default=3)
    parser.add_argument("--posterior-variance", type=float, default=1.5)
    parser.add_argument("--model-id", default=os.environ.get("WATERMARK_PRC_MODEL_ID", "sd2-community/stable-diffusion-2-1-base"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
