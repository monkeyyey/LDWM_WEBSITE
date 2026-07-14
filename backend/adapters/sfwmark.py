from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter


class SfwmarkAdapter(ModelAdapter):
    def command_plan(self, request: WatermarkRequest) -> list[str]:
        wm_type = request.message if request.message in {"Tree-Ring", "RingID", "HSTR", "HSQR"} else "HSQR"
        dataset_id = "coco"
        if request.workflow == "generate":
            return [
                f"cd src && python generate.py --wm_type {wm_type} --dataset_id {dataset_id} --output_dir outputs",
            ]
        if request.workflow in {"detect", "attack"}:
            return [
                f"cd src && python detect.py --wm_type {wm_type} --dataset_id {dataset_id} --output_dir outputs",
            ]
        return []

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        # Real integration target:
        # - generation: invoke SFWMark/src/run.py or the repo's documented script
        # - detection/attack: invoke SFWMark/src/detect.py with selected attacks
        # Keep this adapter responsible for translating our normalized API into
        # repo-specific CLI flags and parsing the repo's output files.
        return self.mock_result(request, score_offset=6)
