import base64
import os
import subprocess
import sys
from pathlib import Path

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
        _, _, encoded = request.image_data_url.partition(",")
        if not encoded:
            return None
        upload_dir = self.project_root / "backend" / "storage" / "uploads" / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = upload_dir / (request.image_name or "upload.png")
        image_path.write_bytes(base64.b64decode(encoded))
        return image_path

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
            raw={"wm_type": wm_type},
        )
