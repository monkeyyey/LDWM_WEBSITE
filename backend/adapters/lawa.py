from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from .repo_process import run_repo_script, runner_python, save_image_input


class LawaAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        script = self.project_root / "backend" / "integrations" / "lawa" / "run_job.py"
        message = request.message
        if len(message) != 48 or any(bit not in "01" for bit in message):
            message = "110111001110110001000000011101000110011100110101"
        operation = "generate" if request.workflow == "generate" else "quality" if request.analysis_mode == "quality" else "extract"
        command = [
            runner_python("WATERMARK_LAWA_PYTHON"),
            str(script),
            "--repo", str(self.repo_path),
            "--operation", operation,
            "--output-dir", str(job_dir),
            "--message", message,
            "--prompt", request.prompt or "A white plate of food on a dining table",
            "--attack", request.attack,
        ]
        if operation == "extract":
            image_path = save_image_input(self.project_root, request, job_id)
            if image_path is None:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing upload", "real", None, ["Upload an image before extraction."], {})
            command.extend(["--image", str(image_path)])
        return run_repo_script(
            project_root=self.project_root,
            request=request,
            job_id=job_id,
            command=command,
            cwd=self.repo_path,
        )
