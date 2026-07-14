from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class WatermarkRequest:
    method: str
    workflow: str
    message: str
    seed: int = 42
    strength: int = 68
    prompt: str = ""
    attack: str = "None"
    image_name: str | None = None
    image_data_url: str | None = None


@dataclass
class WatermarkResult:
    job_id: str
    method: str
    workflow: str
    status: str
    detection_score: int
    recovered_payload: str
    runtime: str
    image_url: str | None
    logs: list[str]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
