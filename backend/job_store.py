from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def storage_root(project_root: Path) -> Path:
    return project_root / "backend" / "storage"


def assign_job_number(project_root: Path, job_id: str, job_dir: Path) -> int:
    metadata_path = job_dir / "metadata.json"
    metadata = _read_json(metadata_path)
    existing = metadata.get("job_number")
    if isinstance(existing, int):
        return existing

    root = storage_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    sequence_path = root / "job_sequence.json"
    sequence = _read_json(sequence_path)
    next_number = sequence.get("next_job_number")
    if not isinstance(next_number, int):
        next_number = _max_existing_job_number(root) + 1

    metadata.update(
        {
            "job_id": job_id,
            "job_number": next_number,
            "created_at": metadata.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    _write_json(metadata_path, metadata)
    _write_json(sequence_path, {"next_job_number": next_number + 1})
    return next_number


def list_sfwmark_jobs(project_root: Path) -> list[dict[str, Any]]:
    outputs_root = storage_root(project_root) / "outputs"
    if not outputs_root.is_dir():
        return []

    candidates = [
        job_dir
        for job_dir in outputs_root.iterdir()
        if job_dir.is_dir()
        and (job_dir / "metadata.json").is_file()
        and (job_dir / "watermarked.png").is_file()
        and (job_dir / "pattern_list-2048.pt").is_file()
        and (job_dir / "identify_gt_indices_1.npy").is_file()
    ]

    for job_dir in sorted(candidates, key=lambda path: path.stat().st_mtime):
        assign_job_number(project_root, job_dir.name, job_dir)

    jobs = []
    for job_dir in sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True):
        metadata = _read_json(job_dir / "metadata.json")
        clean_url = f"/files/outputs/{job_dir.name}/clean.png" if (job_dir / "clean.png").is_file() else None
        jobs.append(
            {
                "job_id": job_dir.name,
                "job_number": metadata.get("job_number"),
                "label": f"Job #{metadata.get('job_number', '?')} - {metadata.get('wm_type', 'SFWMark')}",
                "prompt": metadata.get("prompt", ""),
                "wm_type": metadata.get("wm_type", "HSQR"),
                "model_id": metadata.get("model_id"),
                "created_at": metadata.get("created_at"),
                "image_url": f"/files/outputs/{job_dir.name}/watermarked.png",
                "clean_image_url": clean_url,
            }
        )
    return jobs


def _max_existing_job_number(root: Path) -> int:
    max_number = 0
    outputs_root = root / "outputs"
    if not outputs_root.is_dir():
        return max_number
    for metadata_path in outputs_root.glob("*/metadata.json"):
        job_number = _read_json(metadata_path).get("job_number")
        if isinstance(job_number, int):
            max_number = max(max_number, job_number)
    return max_number


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
