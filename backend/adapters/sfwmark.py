import base64
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from runtimes import sfwmark_lite


class SfwmarkAdapter(ModelAdapter):
    def command_plan(self, request: WatermarkRequest) -> list[str]:
        wm_type = request.message if request.message in {"Tree-Ring", "RingID", "HSTR", "HSQR"} else "HSQR"
        dataset_id = "coco"
        if request.workflow == "generate":
            return [
                f"cd src && python generate.py --wm_type {wm_type} --dataset_id {dataset_id} --output_dir outputs",
            ]
        if request.workflow in {"detect", "attack"}:
            return [
                f"cd src && python detect.py --wm_type {wm_type} --dataset_id {dataset_id} --output_dir outputs",
            ]
        return []

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        if request.workflow == "generate":
            if os.environ.get("SFWMARK_OFFICIAL", "1") == "1":
                return self._run_official_generate(request, job_id, job_dir)
            lite_result = sfwmark_lite.generate(
                prompt=request.prompt or "a clean product photo",
                message=request.message,
                seed=request.seed,
                output_dir=job_dir,
            )
        elif request.workflow in {"detect", "attack"}:
            if os.environ.get("SFWMARK_OFFICIAL", "1") == "1" and request.workflow == "detect":
                return self._run_official_detect(request, job_id, job_dir)
            image_path = self._save_upload(request, job_id)
            if image_path is None:
                return WatermarkResult(
                    job_id=job_id,
                    method=request.method,
                    workflow=request.workflow,
                    status="failed",
                    detection_score=0,
                    recovered_payload="missing upload",
                    runtime="real",
                    image_url=None,
                    logs=["Upload an image before running detection."],
                    raw={},
                )
            lite_result = sfwmark_lite.detect(
                image_path=image_path,
                message=request.message,
                seed=request.seed,
                output_dir=job_dir,
            )
        else:
            return self.mock_result(request, score_offset=6)

        image_url = None
        if lite_result.image_path:
            rel_path = lite_result.image_path.relative_to(self.project_root / "backend" / "storage")
            image_url = f"/files/{rel_path.as_posix()}"
        status = "completed"
        if not image_url and lite_result.detection_score == 0:
            status = "setup_required" if lite_result.recovered_payload in {"setup required", "cuda required"} else "failed"

        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status=status,
            detection_score=lite_result.detection_score,
            recovered_payload=lite_result.recovered_payload,
            runtime="real",
            image_url=image_url,
            logs=lite_result.logs,
            raw=lite_result.raw,
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
        wm_type = request.message if request.message in {"Tree-Ring", "RingID", "HSTR", "HSQR"} else "HSQR"
        runner = self.project_root / "backend" / "integrations" / "sfwmark" / "run_official_generate.py"
        command = [
            sys.executable,
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
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="failed",
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
        clean_path = job_dir / "clean.png"
        clean_url = None
        if clean_path.is_file():
            clean_rel_path = clean_path.relative_to(self.project_root / "backend" / "storage")
            clean_url = f"/files/{clean_rel_path.as_posix()}"
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed",
            detection_score=95,
            recovered_payload=f"{wm_type} official SFWMark image generated",
            runtime="official-sfwmark",
            image_url=f"/files/{rel_path.as_posix()}",
            logs=logs + [f"Generated image: {image_path}"],
            raw={"wm_type": wm_type, "clean_image_url": clean_url},
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
            sys.executable,
            str(runner),
            "--job-id",
            job_id,
            "--source-job-id",
            source_job_id,
            "--image-path",
            str(image_path),
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
            "Running official SFWMark single-image detection adapter.",
            f"Command: {' '.join(command)}",
        ]
        if completed.stdout:
            logs.append(completed.stdout[-6000:])
        if completed.stderr:
            logs.append(completed.stderr[-6000:])

        detect_path = job_dir / "detect.json"
        if completed.returncode != 0 or not detect_path.is_file():
            return WatermarkResult(
                job_id=job_id,
                method=request.method,
                workflow=request.workflow,
                status="failed",
                detection_score=0,
                recovered_payload="official detection failed",
                runtime="official-sfwmark",
                image_url=None,
                logs=logs,
                raw={"returncode": completed.returncode},
            )

        import json

        raw = json.loads(detect_path.read_text(encoding="utf-8"))
        matched = bool(raw.get("matched"))
        score = int(raw.get("score", 0))
        payload = (
            f"matched key {raw.get('key_index')} with distance {raw.get('distance'):.4f}"
            if matched
            else f"not matched; predicted key {raw.get('predicted_index')}, expected {raw.get('key_index')}"
        )
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed" if matched else "failed",
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
