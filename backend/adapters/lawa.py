from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter


class LawaAdapter(ModelAdapter):
    def command_plan(self, request: WatermarkRequest) -> list[str]:
        message = request.message
        if len(message) != 48 or any(bit not in "01" for bit in message):
            message = "110111001110110001000000011101000110011100110101"
        if request.workflow == "generate":
            prompt = request.prompt or "A white plate of food on a dining table"
            return [
                "python inference_AIGC.py "
                "--config configs/SD14_LaWa_inference.yaml "
                "--message_len 48 "
                f"--message '{message}' "
                f"--prompt \"{prompt}\" "
                "--outdir results/SD14_LaWa/txt2img-samples",
            ]
        if request.workflow in {"detect", "attack"}:
            return [
                "# LaWa public code extracts the 48-bit message inside inference_AIGC.py after generation.",
                "# A standalone uploaded-image detector requires a small wrapper around model.decoder(attacked_img).",
            ]
        return []

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        # Real integration target:
        # - invoke LaWa/inference_AIGC.py for generation
        # - use its built-in attack list and test_results_attacks.csv parser
        # - upload-image watermarking may need a separate encoder/decoder wrapper
        #   because the public script is primarily in-generation.
        return self.mock_result(request, score_offset=0)
