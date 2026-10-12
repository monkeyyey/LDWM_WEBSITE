from __future__ import annotations

import json
from pathlib import Path

from adapters import GaussianShadingAdapter, GaussianShannonAdapter, LawaAdapter, PrcWatermarkAdapter, SfwmarkAdapter
from adapters.base import ModelAdapter
from adapters.repository_method import RepositoryMethodAdapter


ADAPTERS = {
    "sfwmark": SfwmarkAdapter,
    "gaussian-shannon": GaussianShannonAdapter,
    "lawa": LawaAdapter,
    "gaussian-shading": GaussianShadingAdapter,
    "prc-watermark": PrcWatermarkAdapter,
}


class MethodRegistry:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        config_path = project_root / "backend" / "config" / "methods.json"
        self.methods = json.loads(config_path.read_text(encoding="utf-8"))
        self.repository_methods = json.loads((config_path.parent / "repository_methods.json").read_text(encoding="utf-8"))
        self.methods.update(self.repository_methods)

    def list_methods(self) -> list[dict]:
        return [
            {"id": method_id, **config}
            for method_id, config in self.methods.items()
        ]

    def get_adapter(self, method_id: str) -> ModelAdapter:
        if method_id not in self.methods:
            raise KeyError(f"Unknown method: {method_id}")

        adapter_class = RepositoryMethodAdapter if method_id in self.repository_methods else ADAPTERS[method_id]
        return adapter_class(method_id, self.methods[method_id], self.project_root)
