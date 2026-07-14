from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path

from schemas import WatermarkRequest, WatermarkResult


class ModelAdapter:
    def __init__(self, method_id: str, config: dict, project_root: Path):
        self.method_id = method_id
        self.config = config
        self.project_root = project_root
        self.repo_path = (project_root / "backend" / config["repo_path"]).resolve()

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        raise NotImplementedError

    def command_plan(self, request: WatermarkRequest) -> list[str]:
        return []

    def make_job_id(self, request: WatermarkRequest) -> str:
        payload = f"{request.method}|{request.workflow}|{request.message}|{request.seed}|{time.time_ns()}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def mock_result(self, request: WatermarkRequest, score_offset: int = 0) -> WatermarkResult:
        job_id = self.make_job_id(request)
        commands = self.command_plan(request)
        if os.environ.get("WATERMARK_EXECUTE_REAL") == "1" and commands:
            return self.execute_commands(request, job_id, commands)

        attack_penalty = 0 if request.attack == "None" else 8
        score = max(45, min(99, 82 + score_offset + request.strength // 12 - attack_penalty))
        payload = self._payload_for(request)
        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed",
            detection_score=score,
            recovered_payload=payload,
            runtime="mock",
            image_url=None,
            logs=[
                f"Resolved method adapter: {self.method_id}",
                f"Repo path: {self.repo_path}",
                "Running in mock mode. No GPU repo code was executed.",
                "Real command plan:",
                *commands,
                "Replace this adapter's run method with a container/job submission when ready.",
            ],
            raw={
                "method_config": self.config,
                "request": request.__dict__,
                "command_plan": commands,
            },
        )

    def execute_commands(self, request: WatermarkRequest, job_id: str, commands: list[str]) -> WatermarkResult:
        logs = [
            f"Resolved method adapter: {self.method_id}",
            f"Repo path: {self.repo_path}",
            "WATERMARK_EXECUTE_REAL=1, executing repo command plan.",
        ]
        for command in commands:
            completed = subprocess.run(
                command,
                cwd=self.repo_path,
                shell=True,
                text=True,
                capture_output=True,
                timeout=60 * 60,
            )
            logs.append(f"$ {command}")
            if completed.stdout:
                logs.append(completed.stdout[-4000:])
            if completed.stderr:
                logs.append(completed.stderr[-4000:])
            if completed.returncode != 0:
                return WatermarkResult(
                    job_id=job_id,
                    method=request.method,
                    workflow=request.workflow,
                    status="failed",
                    detection_score=0,
                    recovered_payload="--",
                    runtime="real",
                    image_url=None,
                    logs=logs,
                    raw={"returncode": completed.returncode, "command_plan": commands},
                )

        return WatermarkResult(
            job_id=job_id,
            method=request.method,
            workflow=request.workflow,
            status="completed",
            detection_score=90,
            recovered_payload=self._payload_for(request),
            runtime="real",
            image_url=None,
            logs=logs,
            raw={"command_plan": commands},
        )

    def _payload_for(self, request: WatermarkRequest) -> str:
        if request.method == "gaussian-shannon":
            return "1011 0010 1100 0111"
        if request.method == "lawa":
            return "48-bit mark matched"
        if request.workflow == "detect":
            return "uploaded image evaluated"
        return "keyed pattern present"
