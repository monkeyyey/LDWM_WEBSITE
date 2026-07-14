import base64
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

        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed" if lite_result.detection_score > 0 else "setup_required",
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
