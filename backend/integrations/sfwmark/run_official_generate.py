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
    parser.add_argument("--wm-type", default="HSQR", choices=["Tree-Ring", "RingID", "HSTR", "HSQR"])
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    sfw_dir = Path(os.environ.get("SFWMARK_REPO", project_root / "external" / "SFWMark")).resolve()
    if not (sfw_dir / "src" / "generate.py").is_file():
        print(f"SFWMark repo not found at {sfw_dir}", file=sys.stderr)
        print("Run: bash backend/integrations/sfwmark/setup_sfwmark.sh", file=sys.stderr)
        return 2

    src_dir = sfw_dir / "src"
    dataset_dir = src_dir / "text_dataset" / "DiffusionDB"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = dataset_dir / "metadata_1k.json"
    metadata_path.write_text(json.dumps([{"prompt": args.prompt}], indent=2), encoding="utf-8")

    output_dir_name = f"web_outputs/{args.job_id}"
    command = [
        sys.executable,
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

    generated = sfw_dir / "src" / output_dir_name / "DB1k" / args.wm_type / "img_pil_wm" / "0.png"
    clean = sfw_dir / "src" / output_dir_name / "DB1k" / args.wm_type / "img_pil" / "0.png"
    pattern = sfw_dir / "src" / output_dir_name / "DB1k" / args.wm_type / "pattern_list-2048.pt"
    identify = sfw_dir / "src" / output_dir_name / "DB1k" / args.wm_type / "identify_gt_indices_1.npy"

    if not generated.is_file():
        print(f"Expected generated image missing: {generated}", file=sys.stderr)
        return 3

    job_dir = project_root / "backend" / "storage" / "outputs" / args.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated, job_dir / "watermarked.png")
    if clean.is_file():
        shutil.copy2(clean, job_dir / "clean.png")
    if pattern.is_file():
        shutil.copy2(pattern, job_dir / "pattern_list-2048.pt")
    if identify.is_file():
        shutil.copy2(identify, job_dir / "identify_gt_indices_1.npy")

    (job_dir / "metadata.json").write_text(
        json.dumps(
            {
                "runner": "official-sfwmark",
                "sfwmark_repo": str(sfw_dir),
                "prompt": args.prompt,
                "wm_type": args.wm_type,
                "dataset_id": "DB1k",
                "source_image": str(generated),
                "clean_image": str(clean) if clean.is_file() else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(job_dir / "watermarked.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
