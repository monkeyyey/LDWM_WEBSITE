from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from schemas import WatermarkRequest, WatermarkResult


class ModelAdapter:
    def __init__(self, method_id: str, config: dict, project_root: Path):
        self.method_id = method_id
        self.config = config
        self.project_root = project_root
        env_name = {
            "sfwmark": "SFWMARK_REPO",
            "gaussian-shannon": "WATERMARK_GS_REPO",
            "lawa": "WATERMARK_LAWA_REPO",
        }.get(method_id)
        override = os.environ.get(env_name) if env_name else None
        configured_path = (project_root / "backend" / config["repo_path"]).resolve()
        external_path = project_root / "external" / configured_path.name
        self.repo_path = Path(override).resolve() if override else configured_path
        if not override and not self.repo_path.is_dir() and external_path.is_dir():
            self.repo_path = external_path.resolve()

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        raise NotImplementedError

    def make_job_id(self, request: WatermarkRequest) -> str:
        payload = f"{request.method}|{request.workflow}|{request.message}|{request.seed}|{time.time_ns()}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
