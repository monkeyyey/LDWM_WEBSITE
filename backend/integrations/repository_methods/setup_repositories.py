"""Clone pinned upstream sources, or audit configuration without loading weights."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from environment import load_environment

CATALOG = json.loads((ROOT / "backend/config/methods.json").read_text())
CATALOG.update(json.loads((ROOT / "backend/config/repository_methods.json").read_text()))
MODULES = {
    "sfwmark": ["diffusers", "utils"],
    "gaussian-shannon": ["diffusers", "ldpc"],
    "lawa": ["models.modifiedAEDecoder", "omegaconf", "augly.image", "clip"],
    "gaussian-shading": ["inverse_stable_diffusion", "watermark"],
    "prc-watermark": ["inversion", "src.prc"],
    "tree-ring": ["inverse_stable_diffusion", "optim_utils"],
    "ring-id": ["inverse_stable_diffusion", "utils"],
    "wind": ["WIND_full", "WIND_fast"],
    "t2smark": ["src.t2s", "src.inversion.inverse_stable_diffusion", "src.utils"],
    "gaussmarker": ["inverse_stable_diffusion", "watermark", "tr_utils", "unet.unet_model", "joblib"],
    "seal": ["inverse_stable_diffusion", "utils", "sentence_transformers"],
    "robin": ["inverse_stable_diffusion", "optim_utils"],
    "tag-wm": ["applied_to_sd2.inverse_stable_diffusion", "applied_to_sd2.watermark_embedder"],
    "serum": ["src.models", "src.evaluation.generate"],
}


def main():
    load_environment()
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=["all", *CATALOG], default="all")
    parser.add_argument("--clone", action="store_true", help="Download missing source checkouts; never overwrite an existing checkout")
    parser.add_argument("--check", action="store_true", help="Check CUDA and imports in each configured Python environment; no model downloads")
    args = parser.parse_args()
    failed = False
    for method, spec in CATALOG.items():
        if args.method not in {"all", method}:
            continue
        repo = Path(os.environ.get(spec["repo_env"], ROOT / "backend" / spec["repo_path"])).expanduser().resolve()
        python = os.environ.get(spec["python_env"], sys.executable)
        print(f"\n{method}: {repo}\n  Python: {python}\n  Profile: {spec['profile']}\n  Artifacts: {', '.join(spec['setup_artifacts']) or 'none'}", flush=True)
        try:
            if args.clone and not repo.exists():
                repo.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["git", "clone", "--no-checkout", spec["repo_url"], str(repo)], check=True)
                subprocess.run(["git", "-C", str(repo), "checkout", "--detach", spec["revision"]], check=True)
            if not repo.is_dir():
                raise RuntimeError("Missing checkout. Run with --clone or configure the repository environment variable.")
            actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            if actual != spec["revision"]:
                raise RuntimeError(f"Revision mismatch: expected {spec['revision']}, got {actual}. Existing checkout left untouched.")
            if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
                raise RuntimeError("Modified tracked upstream files; checkout left untouched.")
            if args.check:
                if method == "robin":
                    (repo / "logs").mkdir(exist_ok=True)
                code = "import torch, importlib; assert torch.cuda.is_available(), 'NVIDIA CUDA unavailable'; "
                if method == "sfwmark":
                    code += f"import sys; sys.path.insert(0, {str(repo / 'src')!r}); "
                code += f"[importlib.import_module(m) for m in {MODULES[method]!r}]; print('CUDA and imports OK; model inference not tested')"
                subprocess.run([python, "-c", code], cwd=repo, check=True, timeout=120)
                for env in spec["setup_artifacts"]:
                    if not os.environ.get(env) or not Path(os.environ[env]).expanduser().is_file():
                        if method == "tag-wm":
                            print(f"  {env} missing: trainfree remains available; trainable requires this artifact")
                        else:
                            raise RuntimeError(f"Missing {env}")
            print("  Source revision OK", flush=True)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failed = True
            print(f"  SETUP REQUIRED: {exc}", flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
