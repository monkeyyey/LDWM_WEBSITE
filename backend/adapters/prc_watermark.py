from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from .repo_process import run_repo_script, runner_python, save_image_input


class PrcWatermarkAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        if request.workflow == "detect" and request.analysis_mode == "identify":
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "PRC-Watermark does not implement candidate-bank identification.", "real", None, ["The released repository returns a keyed binary presence decision."], {})
        if request.workflow not in {"generate", "detect"}:
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "PRC-Watermark exposes generation, Detect, and Decode.", "real", None, ["The released repository does not implement candidate-bank identification."], {})

        if request.submethod_id not in {"", "prc"}:
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "unknown PRC-Watermark submethod", "real", None, ["The released repository exposes one PRC path."], {})
        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        script = self.project_root / "backend" / "integrations" / "prc_watermark" / "run_job.py"
        operation = "generate"
        if request.workflow == "detect":
            operation = request.analysis_mode if request.analysis_mode in {"detect", "decode", "verify"} else "verify"
        command = [
            runner_python("WATERMARK_PRC_PYTHON"),
            str(script),
            "--repo", str(self.repo_path),
            "--operation", operation,
            "--output-dir", str(job_dir),
            "--prompt", request.prompt or "a clean product photo of a ceramic mug on a desk",
            "--seed", str(request.seed),
        ]

        if request.workflow == "generate":
            command.extend([
                "--fpr", str(_option(request, "fpr", 0.00001, float)),
                "--prc-t", str(_option(request, "prc_t", 3, int)),
                "--steps", str(_option(request, "inference_steps", 50, int)),
                "--posterior-variance", str(_option(request, "posterior_variance", 1.5, float)),
            ])
        else:
            image_path = save_image_input(self.project_root, request, job_id)
            if image_path is None:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing analysis image", "real", None, ["Upload an image or choose a PRC-Watermark generation job."], {})
            if not request.source_job_id:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing decoding key", "real", None, ["PRC Detect and Decode require the decoding key saved by a compatible generation job."], {})
            state_dir = self.project_root / "backend" / "storage" / "outputs" / request.source_job_id
            command.extend(["--image", str(image_path), "--state-dir", str(state_dir)])

        return run_repo_script(
            project_root=self.project_root,
            request=request,
            job_id=job_id,
            command=command,
            cwd=self.repo_path,
        )


def _option(request: WatermarkRequest, name: str, default, value_type):
    value = request.options.get(name, default)
    try:
        return value_type(value)
    except (TypeError, ValueError):
        return default
