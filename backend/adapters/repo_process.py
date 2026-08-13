from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from schemas import WatermarkRequest, WatermarkResult
from job_store import record_generation_job


def save_image_input(project_root: Path, request: WatermarkRequest, job_id: str) -> Path | None:
    """Persist a data URL or an existing backend file for a repository runner."""
    if not request.image_data_url:
        return None
    if not request.image_data_url.startswith("data:"):
        parsed = urlparse(request.image_data_url)
        requested = parsed.path if parsed.scheme else request.image_data_url
        if not requested.startswith("/files/"):
            return None
        storage_root = (project_root / "backend" / "storage").resolve()
        file_path = (storage_root / requested.removeprefix("/files/")).resolve()
        return file_path if storage_root in file_path.parents and file_path.is_file() else None

    _, _, encoded = request.image_data_url.partition(",")
    if not encoded:
        return None
    upload_dir = project_root / "backend" / "storage" / "uploads" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = upload_dir / (request.image_name or "upload.png")
    image_path.write_bytes(base64.b64decode(encoded))
    return image_path


def run_repo_script(
    *,
    project_root: Path,
    request: WatermarkRequest,
    job_id: str,
    command: list[str],
    cwd: Path,
    timeout: int = 7200,
) -> WatermarkResult:
    logs = [
        f"Resolved method adapter: {request.method}",
        f"Repository runner cwd: {cwd}",
        "$ " + " ".join(command),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="failed",
            detection_score=0,
            recovered_payload="runner timed out",
            runtime="real",
            image_url=None,
            logs=logs + [f"Runner exceeded {timeout} seconds.", str(exc)],
            raw={"command": command},
        )
    except OSError as exc:
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="setup_required",
            detection_score=0,
            recovered_payload="runner unavailable",
            runtime="real",
            image_url=None,
            logs=logs + [f"Could not start repository runner: {exc}"],
            raw={"command": command},
        )

    if completed.stdout:
        logs.append(completed.stdout[-12000:])
    if completed.stderr:
        logs.append(completed.stderr[-12000:])

    payload = _result_marker(completed.stdout)
    if completed.returncode != 0 or payload is None:
        missing_dependency = any("ModuleNotFoundError" in line or "No module named" in line for line in logs)
        status = "setup_required" if missing_dependency else "failed"
        recovered = "repository environment required" if missing_dependency else "repository runner failed"
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status=status,
            detection_score=0,
            recovered_payload=recovered,
            runtime="real",
            image_url=None,
            logs=logs + [f"Runner exit code: {completed.returncode}"],
            raw={"returncode": completed.returncode, "command": command},
        )

    image_url = _storage_url(project_root, payload.get("image_path"))
    raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
    raw.update({"command": command, "runner_stdout": completed.stdout[-4000:]})
    if request.workflow == "generate" and payload.get("status", "completed") == "completed" and image_url:
        raw["job_number"] = record_generation_job(project_root, job_id, request)
    return WatermarkResult(
        job_id=job_id,
        method=request.method,
        workflow=request.workflow,
        status=str(payload.get("status", "completed")),
        detection_score=int(payload.get("detection_score", 0)),
        recovered_payload=str(payload.get("recovered_payload", "--")),
        runtime="real",
        image_url=image_url,
        logs=logs,
        raw=raw,
    )


def runner_python(env_name: str) -> str:
    return os.environ.get(env_name, sys.executable)


def _result_marker(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith("@@RESULT@@"):
            try:
                return json.loads(line.removeprefix("@@RESULT@@"))
            except json.JSONDecodeError:
                return None
    return None


def _storage_url(project_root: Path, image_path: Any) -> str | None:
    if not image_path:
        return None
    path = Path(str(image_path)).resolve()
    storage_root = (project_root / "backend" / "storage").resolve()
    if storage_root not in path.parents or not path.is_file():
        return None
    return f"/files/{path.relative_to(storage_root).as_posix()}"
