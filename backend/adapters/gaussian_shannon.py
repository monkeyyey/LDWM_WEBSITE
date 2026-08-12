from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from .repo_process import run_repo_script, runner_python, save_image_input


class GaussianShannonAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        if request.workflow not in {"generate", "detect"}:
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "Gaussian-Shannon exposes generation and verification through message extraction.", "real", None, ["The selected workflow is not part of the application core."], {})
        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        script = self.project_root / "backend" / "integrations" / "gaussian_shannon" / "run_job.py"
        coding = "ldpc" if request.submethod_id == "ldpc" else "gaussian"
        command = [
            runner_python("WATERMARK_GS_PYTHON"),
            str(script),
            "--repo", str(self.repo_path),
            "--coding", coding,
            "--message", request.message,
            "--prompt", request.prompt or "a clean product photo of a ceramic mug on a desk",
            "--seed", str(request.seed),
            "--operation", "generate" if request.workflow == "generate" else "extract",
            "--output-dir", str(job_dir),
        ]
        if request.workflow != "generate":
            image_path = save_image_input(self.project_root, request, job_id)
            if image_path is None:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing upload", "real", None, ["Upload an image before extraction."], {})
            command.extend(["--image", str(image_path)])
            if request.source_job_id:
                state_dir = self.project_root / "backend" / "storage" / "outputs" / request.source_job_id
                if state_dir.is_dir():
                    command.extend(["--state-dir", str(state_dir)])
        return run_repo_script(
            project_root=self.project_root,
            request=request,
            job_id=job_id,
            command=command,
            cwd=self.repo_path,
        )
