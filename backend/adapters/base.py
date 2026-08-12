from __future__ import annotations

import hashlib
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

    def make_job_id(self, request: WatermarkRequest) -> str:
        payload = f"{request.method}|{request.workflow}|{request.message}|{request.seed}|{time.time_ns()}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
