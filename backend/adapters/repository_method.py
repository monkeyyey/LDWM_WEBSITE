from __future__ import annotations

import json
import math
import os
import re

from schemas import WatermarkRequest, WatermarkResult
from .base import ModelAdapter
from .repo_process import run_repo_script, runner_python, save_image_input


def validated_options(config, options):
    if not isinstance(options, dict):
        raise ValueError("Options must be an object")
    result = {}
    for key, spec in config["options"].items():
        value = options.get(key, spec["default"])
        if spec["type"] in {"select", "toggle"}:
            if isinstance(value, bool) or value not in spec["choices"]:
                raise ValueError(f"Invalid {key}: choose one of {spec['choices']}")
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            if not spec["min"] <= value <= spec["max"]:
                raise ValueError(f"{key} must be between {spec['min']} and {spec['max']}")
            if spec["step"] == 1 and value != int(value):
                raise ValueError(f"{key} must be an integer")
            if spec["step"] == 1:
                value = int(value)
        result[key] = value
    if "key_index" in result and result["key_index"] >= result["assigned_keys"]:
        raise ValueError("Pattern index must be smaller than the candidate pattern count")
    if config["name"] == "ROBIN":
        if result["injection_step"] >= min(result["inference_steps"], result["inversion_steps"]):
            raise ValueError("Injection step must be below both generation and inversion steps")
        if result["w_low_radius"] >= result["w_up_radius"]:
            raise ValueError("Inner radius must be smaller than outer radius")
    return result


class RepositoryMethodAdapter(ModelAdapter):
    """Shared process boundary; each runner calls its own upstream algorithm."""

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        job_id = self.make_job_id(request)

        def error(status, message):
            return WatermarkResult(job_id, request.method, request.workflow, status, 0, message, "real", None, [message], {})

        operation = "generate" if request.workflow == "generate" else request.analysis_mode
        if request.workflow not in {"generate", "detect"} or operation not in self.config["adapter_workflows"]:
            return error("unsupported", "This operation is not available for the selected repository")
        if request.submethod_id not in self.config["variants"]:
            return error("unsupported", "Unknown repository variant")
        try:
            if isinstance(request.seed, bool) or not isinstance(request.seed, int) or not 0 <= request.seed < 2**32:
                raise ValueError("Seed must be an integer between 0 and 4294967295")
            options = validated_options(self.config, request.options)
            state_dir = None
            if operation != "generate":
                if not re.fullmatch(r"[a-f0-9]{12}", request.source_job_id or ""):
                    raise ValueError("Select a compatible generation job before analysis")
                state_dir = self.project_root / "backend/storage/outputs" / request.source_job_id
                metadata_path = state_dir / "metadata.json"
                if not metadata_path.is_file():
                    raise ValueError("Generation metadata is missing")
                state = json.loads(metadata_path.read_text())
                if state.get("method") != request.method or state.get("submethod_id") != request.submethod_id:
                    raise ValueError("The generation job belongs to another method or variant")
                if state.get("expected_revision") != self.config["revision"] or not (state_dir / "private.pt").is_file():
                    raise ValueError("Generation state is missing or belongs to an incompatible repository revision")
                # Analysis always uses the parameters bound to the saved keys.
                options = validated_options(self.config, state["options"])
            if not self.repo_path.is_dir():
                return error("setup_required", f"Clone {self.config['repo_url']} into {self.repo_path}. See docs/REPOSITORY_METHOD_SETUP.md")
            image_path = None
            if operation != "generate":
                image_path = save_image_input(self.project_root, request, job_id)
                if image_path is None:
                    raise ValueError("Choose a generated image or upload an image to analyze")
            job_dir = self.project_root / "backend/storage/outputs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "method": request.method, "variant": request.submethod_id, "operation": operation,
                "prompt": request.prompt, "message": request.message, "seed": request.seed,
                "model_id": os.environ.get(self.config["model_env"], self.config["default_model"]),
                "options": options, "repo": str(self.repo_path), "output_dir": str(job_dir),
                "state_dir": str(state_dir) if state_dir else None,
                "image": str(image_path) if image_path else None, "expected_revision": self.config["revision"],
            }
            request_path = job_dir / "request.json"
            request_path.write_text(json.dumps(payload, indent=2))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            return error("failed", str(exc))
        script = self.project_root / "backend/integrations/repository_methods/run_job.py"
        return run_repo_script(
            project_root=self.project_root, request=request, job_id=job_id,
            command=[runner_python(self.config["python_env"]), str(script), "--request", str(request_path)],
            cwd=self.repo_path,
        )
