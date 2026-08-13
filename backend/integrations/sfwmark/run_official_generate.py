from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run official SFWMark generation for one website prompt.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--wm-type", default="HSQR", choices=["HSTR", "HSQR"])
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    sfw_dir = configured_repo(project_root)
    if not (sfw_dir / "src" / "generate.py").is_file():
        print(f"SFWMark repo not found at {sfw_dir}", file=sys.stderr)
        print("Run: bash backend/integrations/sfwmark/setup_sfwmark.sh", file=sys.stderr)
        return 2

    src_dir = sfw_dir / "src"
    model_id = os.environ.get("SFW_MODEL_ID", "sd2-community/stable-diffusion-2-1-base")

    dataset_dir = src_dir / "text_dataset" / "DiffusionDB"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = dataset_dir / "metadata_1k.json"
    metadata_path.write_text(json.dumps([{"prompt": args.prompt}], indent=2), encoding="utf-8")

    output_dir_name = f"web_outputs/{args.job_id}"
    command = [
        os.environ.get("SFWMARK_PYTHON", sys.executable),
        "generate.py",
        "--wm_type",
        args.wm_type,
        "--dataset_id",
        "DB1k",
        "--output_dir",
        output_dir_name,
    ]

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    completed = subprocess.run(command, cwd=src_dir, text=True, env=env)
    if completed.returncode != 0:
        return completed.returncode

    output_base = sfw_dir / output_dir_name / "DB1k" / args.wm_type
    generated = first_png(output_base / "img_pil_wm")
    pattern = output_base / "pattern_list-2048.pt"
    identify = output_base / "identify_gt_indices_1.npy"

    if generated is None:
        print(f"Expected generated image missing under: {output_base / 'img_pil_wm'}", file=sys.stderr)
        return 3
    if not pattern.is_file() or not identify.is_file():
        missing = [str(path) for path in (pattern, identify) if not path.is_file()]
        print(f"SFWMark generation artifacts missing: {', '.join(missing)}", file=sys.stderr)
        return 3

    job_dir = project_root / "backend" / "storage" / "outputs" / args.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated, job_dir / "watermarked.png")
    shutil.copy2(pattern, job_dir / "pattern_list-2048.pt")
    shutil.copy2(identify, job_dir / "identify_gt_indices_1.npy")

    (job_dir / "metadata.json").write_text(
        json.dumps(
            {
                "runner": "official-sfwmark",
                "method": "sfwmark",
                "submethod_id": args.wm_type.lower(),
                "sfwmark_repo": str(sfw_dir),
                "prompt": args.prompt,
                "wm_type": args.wm_type,
                "model_id": model_id,
                "dataset_id": "DB1k",
                "source_image": str(generated),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(job_dir / "watermarked.png")
    return 0


def first_png(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    return next(iter(sorted(directory.glob("*.png"))), None)


def configured_repo(project_root: Path) -> Path:
    configured = os.environ.get("SFWMARK_REPO")
    if configured:
        return Path(configured).resolve()
    checked_in = project_root / "work" / "repos" / "SFWMark"
    return checked_in if checked_in.is_dir() else (project_root / "external" / "SFWMark").resolve()


if __name__ == "__main__":
    raise SystemExit(main())
