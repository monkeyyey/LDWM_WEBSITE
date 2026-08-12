import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from job_store import assign_job_number


class SfwmarkAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        if request.workflow == "generate":
            return self._run_official_generate(request, job_id, job_dir)
        if request.workflow == "detect":
            return self._run_official_detect(request, job_id, job_dir)
        return self._unsupported(request, job_id)

    def _unsupported(self, request: WatermarkRequest, job_id: str) -> WatermarkResult:
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="unsupported",
            detection_score=0,
            recovered_payload="This SFWMark adapter exposes generation, verification, and identification only.",
            runtime="official-sfwmark",
            image_url=None,
            logs=["The selected action is not wired to an original SFWMark repository workflow."],
            raw={},
        )

    def _save_upload(self, request: WatermarkRequest, job_id: str) -> Path | None:
        if not request.image_data_url:
            return None
        if not request.image_data_url.startswith("data:"):
            resolved = self._resolve_storage_url(request.image_data_url)
            if resolved is not None:
                return resolved
            return None
        _, _, encoded = request.image_data_url.partition(",")
        if not encoded:
            return None
        upload_dir = self.project_root / "backend" / "storage" / "uploads" / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = upload_dir / (request.image_name or "upload.png")
        image_path.write_bytes(base64.b64decode(encoded))
        return image_path

    def _resolve_storage_url(self, image_url: str) -> Path | None:
        parsed = urlparse(image_url)
        path = parsed.path if parsed.scheme else image_url
        if not path.startswith("/files/"):
            return None
        storage_root = (self.project_root / "backend" / "storage").resolve()
        requested = path.removeprefix("/files/")
        file_path = (storage_root / requested).resolve()
        if storage_root not in file_path.parents and file_path != storage_root:
            return None
        return file_path if file_path.is_file() else None

    def _run_official_generate(self, request: WatermarkRequest, job_id: str, job_dir: Path) -> WatermarkResult:
        wm_type = request.message if request.message in {"HSTR", "HSQR"} else "HSQR"
        runner = self.project_root / "backend" / "integrations" / "sfwmark" / "run_official_generate.py"
        command = [
            os.environ.get("SFWMARK_PYTHON", sys.executable),
            str(runner),
            "--prompt",
            request.prompt or "a clean product photo",
            "--wm-type",
            wm_type,
            "--job-id",
            job_id,
            "--project-root",
            str(self.project_root),
        ]
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            text=True,
            capture_output=True,
            timeout=60 * 60,
        )
        logs = [
            "Running official SFWMark generation adapter.",
            f"Command: {' '.join(command)}",
        ]
        if completed.stdout:
            logs.append(completed.stdout[-6000:])
        if completed.stderr:
            logs.append(completed.stderr[-6000:])

        image_path = job_dir / "watermarked.png"
        if completed.returncode != 0 or not image_path.is_file():
            setup_required = "ModuleNotFoundError" in completed.stderr or "No module named" in completed.stderr
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="setup_required" if setup_required else "failed",
                detection_score=0,
                recovered_payload="official generation failed",
                runtime="official-sfwmark",
                image_url=None,
                logs=logs
                + [
                    "If this failed on AWS, run: bash backend/integrations/sfwmark/setup_sfwmark.sh",
                    "Then run: bash backend/integrations/sfwmark/smoke_official_generate.sh",
                ],
                raw={"returncode": completed.returncode},
            )

        rel_path = image_path.relative_to(self.project_root / "backend" / "storage")
        job_number = assign_job_number(self.project_root, job_id, job_dir)
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed",
            detection_score=0,
            recovered_payload=f"{wm_type} official SFWMark image generated",
            runtime="official-sfwmark",
            image_url=f"/files/{rel_path.as_posix()}",
            logs=logs + [f"Generated image: {image_path}"],
            raw={"wm_type": wm_type, "job_number": job_number},
        )

    def _run_official_detect(self, request: WatermarkRequest, job_id: str, job_dir: Path) -> WatermarkResult:
        image_path = self._save_upload(request, job_id)
        source_job_id = request.source_job_id or self._infer_source_job_id(request.image_data_url)
        if image_path is None:
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="failed",
                detection_score=0,
                recovered_payload="missing upload",
                runtime="official-sfwmark",
                image_url=None,
                logs=["Upload an image, or detect the image generated by this website."],
                raw={},
            )
        if not source_job_id:
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="failed",
                detection_score=0,
                recovered_payload="missing source job",
                runtime="official-sfwmark",
                image_url=None,
                logs=[
                    "SFWMark detection needs the generation job artifacts: pattern_list-2048.pt and identify_gt_indices_1.npy.",
                    "Generate an SFWMark image in this website first, then run Detect on that generated image.",
                ],
                raw={},
            )

        runner = self.project_root / "backend" / "integrations" / "sfwmark" / "run_official_detect_single.py"
        command = [
            os.environ.get("SFWMARK_PYTHON", sys.executable),
            str(runner),
            "--job-id",
            job_id,
            "--source-job-id",
            source_job_id,
            "--image-path",
            str(image_path),
            "--project-root",
            str(self.project_root),
            "--analysis-mode",
            request.analysis_mode if request.analysis_mode in {"verify", "identify"} else "verify",
        ]
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            text=True,
            capture_output=True,
            timeout=60 * 60,
        )
        logs = [
            "Running official SFWMark single-image detection adapter.",
            f"Command: {' '.join(command)}",
        ]
        if completed.stdout:
            logs.append(completed.stdout[-6000:])
        if completed.stderr:
            logs.append(completed.stderr[-6000:])

        detect_path = job_dir / "detect.json"
        if completed.returncode != 0 or not detect_path.is_file():
            setup_required = "ModuleNotFoundError" in completed.stderr or "No module named" in completed.stderr
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="setup_required" if setup_required else "failed",
                detection_score=0,
                recovered_payload="official detection failed",
                runtime="official-sfwmark",
                image_url=None,
                logs=logs,
                raw={"returncode": completed.returncode},
            )

        raw = json.loads(detect_path.read_text(encoding="utf-8"))
        identified = bool(raw.get("identified"))
        analysis_mode = raw.get("analysis_mode", request.analysis_mode or "verify")
        distance = float(raw.get("verification_distance", raw.get("distance", 0.0)))
        if analysis_mode == "identify":
            score = 100 if identified else 0
            payload = f"predicted key {raw.get('predicted_index')}; identification {'correct' if identified else 'incorrect'}"
        else:
            score = 0
            payload = f"verification distance {distance:.4f} against expected key {raw.get('key_index')}"
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed",
            detection_score=score,
            recovered_payload=payload,
            runtime="official-sfwmark",
            image_url=None,
            logs=logs + [f"Detection result: {payload}"],
            raw=raw,
        )

    def _infer_source_job_id(self, image_data_url: str | None) -> str | None:
        if not image_data_url:
            return None
        parsed = urlparse(image_data_url)
        path = parsed.path if parsed.scheme else image_data_url
        parts = Path(path).parts
        if "outputs" not in parts:
            return None
        index = parts.index("outputs")
        return parts[index + 1] if len(parts) > index + 1 else None
