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


def record_generation_job(project_root: Path, job_id: str, request: Any) -> int:
    """Persist the common history fields for a completed repository run."""
    job_dir = storage_root(project_root) / "outputs" / job_id
    metadata_path = job_dir / "metadata.json"
    metadata = _read_json(metadata_path)
    metadata.update(
        {
            "method": request.method,
            "submethod_id": request.submethod_id,
            "workflow": "generate",
        }
    )
    metadata.setdefault("message", request.message)
    metadata.setdefault("prompt", request.prompt)
    metadata.setdefault("seed", request.seed)
    _write_json(metadata_path, metadata)
    return assign_job_number(project_root, job_id, job_dir)


def list_generation_jobs(
    project_root: Path,
    method_id: str | None = None,
    submethod_id: str | None = None,
) -> list[dict[str, Any]]:
    outputs_root = storage_root(project_root) / "outputs"
    if not outputs_root.is_dir():
        return []

    candidates = [
        job_dir
        for job_dir in outputs_root.iterdir()
        if job_dir.is_dir()
        and (job_dir / "metadata.json").is_file()
        and (job_dir / "watermarked.png").is_file()
    ]

    for job_dir in sorted(candidates, key=lambda path: path.stat().st_mtime):
        assign_job_number(project_root, job_dir.name, job_dir)

    jobs = []
    for job_dir in sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True):
        metadata = _read_json(job_dir / "metadata.json")
        resolved_method = metadata.get("method") or _infer_method(metadata, job_dir)
        resolved_submethod = metadata.get("submethod_id") or _infer_submethod(metadata, resolved_method)
        if method_id and resolved_method != method_id:
            continue
        if submethod_id and resolved_submethod != submethod_id:
            continue
        jobs.append(
            {
                "job_id": job_dir.name,
                "job_number": metadata.get("job_number"),
                "label": f"Job #{metadata.get('job_number', '?')} - {resolved_method} / {resolved_submethod}",
                "prompt": metadata.get("prompt", ""),
                "method": resolved_method,
                "submethod_id": resolved_submethod,
                "wm_type": metadata.get("wm_type"),
                "message": _display_message(metadata.get("message"), resolved_method),
                "model_id": metadata.get("model_id"),
                "created_at": metadata.get("created_at"),
                "image_url": f"/files/outputs/{job_dir.name}/watermarked.png",
            }
        )
    return jobs


def _display_message(message: Any, method_id: str) -> str | None:
    """Normalize repository metadata before it reaches the frontend."""
    if message is None:
        return None
    if method_id not in {"gaussian-shannon", "gaussian-shading"}:
        return str(message)
    if isinstance(message, list):
        return "".join(str(int(bit)) for bit in message)
    return str(message)


def list_sfwmark_jobs(project_root: Path) -> list[dict[str, Any]]:
    """Backward-compatible SFWMark history view."""
    return list_generation_jobs(project_root, method_id="sfwmark")


def _infer_method(metadata: dict[str, Any], job_dir: Path) -> str:
    if metadata.get("wm_type") or (job_dir / "pattern_list-2048.pt").is_file():
        return "sfwmark"
    if metadata.get("coding"):
        return "gaussian-shannon"
    if metadata.get("config") == "configs/SD14_LaWa_inference.yaml":
        return "lawa"
    if metadata.get("gaussian_shading_variant"):
        return "gaussian-shading"
    if metadata.get("prc_t"):
        return "prc-watermark"
    return "unknown"


def _infer_submethod(metadata: dict[str, Any], method_id: str) -> str:
    if method_id == "sfwmark":
        return str(metadata.get("wm_type", "HSQR")).lower()
    if method_id == "gaussian-shannon":
        return str(metadata.get("coding", "gaussian"))
    if method_id == "lawa":
        return "lawa-48"
    if method_id == "gaussian-shading":
        return str(metadata.get("gaussian_shading_variant", "chacha"))
    if method_id == "prc-watermark":
        return "prc"
    return ""


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
