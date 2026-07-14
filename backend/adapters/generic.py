from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter


class GenericAdapter(ModelAdapter):
    def run(self, request: WatermarkRequest) -> WatermarkResult:
        return self.mock_result(request, score_offset=-3)
