"""Isolated entry point. Import algorithm code only from a pinned upstream checkout."""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback


class SetupRequired(Exception):
    pass


def checkpoint(name):
    path = Path(os.environ.get(name, "")).expanduser()
    if not os.environ.get(name) or not path.is_file():
        raise SetupRequired(f"Set {name} to a trusted local checkpoint file. See docs/REPOSITORY_METHOD_SETUP.md")
    return path.resolve()


def move(value, device):
    import torch
    if isinstance(value, torch.Tensor):
        return value.to(device)
    if isinstance(value, dict):
        return {k: move(v, device) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(move(v, device) for v in value)
    return value


def serializable_cpu(value):
    """Move private state to CPU and widen complex-half tensors for PyTorch 1.13 serialization."""
    import torch
    if isinstance(value, torch.Tensor):
        if value.dtype == torch.complex32:
            value = value.to(torch.complex64)
        return value.to("cpu")
    if isinstance(value, dict):
        return {key: serializable_cpu(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serializable_cpu(item) for item in value]
    if isinstance(value, tuple):
        return tuple(serializable_cpu(item) for item in value)
    return value


def load_trusted(path, device="cpu"):
    import torch
    # State is server-created, never accepted as an uploaded pickle/checkpoint.
    return torch.load(path, map_location=device, weights_only=False)


class Context:
    def __init__(self, request):
        self.request = request
        self.output = Path(request["output_dir"])
        self.generate = request["operation"] == "generate"
        self.metadata = {}
        self.state = {}
        if not self.generate:
            source = Path(request["state_dir"])
            self.metadata = json.loads((source / "metadata.json").read_text())
            for field in ("model_id", "options", "seed"):
                request[field] = self.metadata[field]
            self.state = load_trusted(source / "private.pt", "cuda")
        self.options = request["options"]
        self.model = request["model_id"]
        self.device = "cuda"

    def save(self, image, state, **metadata):
        import torch
        self.output.mkdir(parents=True, exist_ok=True)
        private = self.output / "private.pt"
        torch.save(serializable_cpu(state), private)
        private.chmod(0o600)
        image.save(self.output / "watermarked.png")
        fields = {k: self.request[k] for k in ("method", "prompt", "seed", "model_id", "options", "expected_revision")}
        fields.update(submethod_id=self.request["variant"], workflow="generate", **metadata)
        (self.output / "metadata.json").write_text(json.dumps(fields, indent=2))
        return {"image_path": str(self.output / "watermarked.png"), "recovered_payload": "Generation complete; private state saved", "raw": {"summary": "Generated with the upstream algorithm. GPU validation is environment-specific.", "revision": self.request["expected_revision"]}}

    def image(self):
        from PIL import Image
        with Image.open(self.request["image"]) as image:
            return image.convert("RGB")

    def metrics(self, summary, values, payload="--", **extra):
        metrics = []
        for label, value in values.items():
            if isinstance(value, float):
                value = round(value, 6) if math.isfinite(value) else "No finite match"
            metrics.append({"label": label, "value": value})
        return {"recovered_payload": payload, "raw": {"summary": summary, "metrics": metrics, **extra}}


def preflight(request, catalog):
    spec = catalog[request["method"]]
    revision = subprocess.check_output(["git", "-C", request["repo"], "rev-parse", "HEAD"], text=True).strip()
    if revision != spec["revision"]:
        raise SetupRequired(f"Expected {spec['revision']} in {request['repo']}; found {revision}. Use the pinned setup instructions.")
    dirty = subprocess.check_output(["git", "-C", request["repo"], "status", "--porcelain", "--untracked-files=no"], text=True).strip()
    if dirty:
        raise SetupRequired("The upstream checkout has modified tracked files. Use a clean pinned checkout; your files have not been changed.")
    if request["method"] == "gaussmarker":
        checkpoint("WATERMARK_GAUSSMARKER_GNR")
        if request["operation"] == "generate":
            checkpoint("WATERMARK_GAUSSMARKER_W1")
    elif request["method"] == "robin" and request["operation"] == "generate":
        checkpoint("WATERMARK_ROBIN_CHECKPOINT")
    elif request["method"] == "tag-wm" and request["variant"] == "trainable":
        checkpoint("WATERMARK_TAG_WM_DVRD")
    elif request["method"] == "serum" and request["operation"] == "generate":
        for key in ("CONFIG", "WATERMARK", "DETECTOR"):
            checkpoint("WATERMARK_SERUM_" + key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    catalog = json.loads((Path(__file__).resolve().parents[2] / "config/repository_methods.json").read_text())
    try:
        preflight(request, catalog)
        sys.path.insert(0, request["repo"])
        os.chdir(request["repo"])
        if request["method"] == "robin":
            (Path(request["repo"]) / "logs").mkdir(exist_ok=True)
        os.environ.setdefault("WANDB_MODE", "disabled")
        import torch
        if not torch.cuda.is_available():
            raise SetupRequired("These upstream integrations require NVIDIA CUDA. Configure a method-specific Python environment on your GPU server.")
        context = Context(request)
        import random
        import numpy as np
        random.seed(request["seed"])
        np.random.seed(request["seed"])
        torch.manual_seed(request["seed"])
        torch.cuda.manual_seed_all(request["seed"])
        method = request["method"]
        module = "noise_methods" if method in {"tree-ring", "ring-id", "wind", "t2smark"} else "advanced_methods"
        handler = getattr(importlib.import_module(module), method.replace("-", "_"))
        with torch.no_grad():
            result = handler(context)
        result.setdefault("status", "completed")
    except (SetupRequired, ImportError, FileNotFoundError) as exc:
        result = {"status": "setup_required", "recovered_payload": str(exc), "raw": {"summary": str(exc)}}
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        result = {"status": "failed", "recovered_payload": str(exc), "raw": {"summary": str(exc)}}
    print("@@RESULT@@" + json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    sys.modules["run_job"] = sys.modules[__name__]
    main()
