from schemas import WatermarkRequest, WatermarkResult

from .base import ModelAdapter


class GaussianShannonAdapter(ModelAdapter):
    def command_plan(self, request: WatermarkRequest) -> list[str]:
        if request.workflow == "generate":
            return [
                "python - <<'PY'\n"
                "from infer import multi_generate_gauss\n"
                "multi_generate_gauss(gen_index='web_job')\n"
                "PY",
            ]
        if request.workflow in {"detect", "attack"}:
            return [
                "# Put uploaded/generated images in eval/generated_watermark/web_job_input/",
                "python - <<'PY'\n"
                "from infer import robustness_gauss_test\n"
                "robustness_gauss_test('eval/generated_watermark/web_job_input', gen_index='web_job', sum=8)\n"
                "PY",
            ]
        return []

    def run(self, request: WatermarkRequest) -> WatermarkResult:
        # Real integration target:
        # - invoke Gaussian-Shannon/infer.py
        # - map message text into the repo's expected bit payload
        # - parse LDPC/majority-vote recovery results into recovered_payload
        # - expose advanced_embedding_attack as an attack-test backend option
        return self.mock_result(request, score_offset=2)
