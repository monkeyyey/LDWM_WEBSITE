from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter
from .repo_process import run_repo_script, runner_python, save_image_input


class GaussianShadingAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)
        if request.workflow == "detect" and request.analysis_mode == "identify":
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "Gaussian Shading does not implement candidate-bank identification.", "real", None, ["The repository's traceability threshold is part of known-watermark verification."], {})
        if request.workflow not in {"generate", "detect"}:
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "Gaussian Shading exposes generation and keyed verification.", "real", None, ["The upstream repository has no candidate-bank identification workflow."], {})

        job_dir = self.project_root / "backend" / "storage" / "outputs" / job_id
        script = self.project_root / "backend" / "integrations" / "gaussian_shading" / "run_job.py"
        if request.submethod_id not in {"simple", "chacha"}:
            return WatermarkResult(job_id, request.method, request.workflow, "unsupported", 0, "unknown Gaussian Shading variant", "real", None, ["Choose the upstream simple or chacha variant."], {})
        variant = request.submethod_id
        command = [
            runner_python("WATERMARK_GSHADING_PYTHON"),
            str(script),
            "--repo", str(self.repo_path),
            "--operation", "generate" if request.workflow == "generate" else "verify",
            "--variant", variant,
            "--output-dir", str(job_dir),
            "--prompt", request.prompt or "a clean product photo of a ceramic mug on a desk",
            "--seed", str(request.seed),
        ]

        if request.workflow == "generate":
            command.extend([
                "--channel-copy", str(_option(request, "channel_copy", 1, int)),
                "--hw-copy", str(_option(request, "hw_copy", 8, int)),
                "--fpr", str(_option(request, "fpr", 0.000001, float)),
                "--user-number", str(_option(request, "user_number", 1000000, int)),
                "--steps", str(_option(request, "inference_steps", 50, int)),
            ])
        else:
            image_path = save_image_input(self.project_root, request, job_id)
            if image_path is None:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing analysis image", "real", None, ["Upload an image or choose a Gaussian Shading generation job."], {})
            if not request.source_job_id:
                return WatermarkResult(job_id, request.method, request.workflow, "failed", 0, "missing source key", "real", None, ["Gaussian Shading verification requires the key and watermark saved by a compatible generation job."], {})
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
