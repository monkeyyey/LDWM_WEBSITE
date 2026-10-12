"""CPU contract tests. These do not claim CUDA/model quality validation."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/integrations/repository_methods"))

from adapters.repository_method import RepositoryMethodAdapter, validated_options
from adapters.repo_process import _result_marker, save_image_input
from registry import MethodRegistry
from schemas import WatermarkRequest
from run_job import Context, SetupRequired, preflight

CATALOG = json.loads((ROOT / "backend/config/repository_methods.json").read_text())


class AdapterContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(CATALOG["tree-ring"], repo_path="../repo")
        (self.root / "repo").mkdir()
        self.adapter = RepositoryMethodAdapter("tree-ring", self.config, self.root)

    def request(self, **kwargs):
        args = dict(method="tree-ring", workflow="generate", message="", submethod_id="ring", prompt="test", seed=42)
        args.update(kwargs)
        return WatermarkRequest(**args)

    def test_model_revision_defaults_to_fp16_and_can_be_overridden(self):
        import noise_methods
        from types import SimpleNamespace

        context = SimpleNamespace(request={"method": "tree-ring"})
        self.assertEqual(noise_methods.pipeline_revision(context), "fp16")
        with patch.dict("os.environ", {"WATERMARK_TREE_RING_MODEL_REVISION": "main"}):
            self.assertEqual(noise_methods.pipeline_revision(context), "main")

    def source(self, **overrides):
        source = self.root / "backend/storage/outputs/123456abcdef"
        source.mkdir(parents=True)
        metadata = dict(method="tree-ring", submethod_id="ring", expected_revision=self.config["revision"],
                        options={"inference_steps": 25}, model_id="saved-model", seed=15)
        metadata.update(overrides)
        (source / "metadata.json").write_text(json.dumps(metadata))
        (source / "private.pt").touch()
        return source

    def test_all_nine_have_dispatchers_and_valid_defaults(self):
        import noise_methods
        import advanced_methods
        for method, config in CATALOG.items():
            with self.subTest(method=method):
                self.assertTrue(callable(getattr(noise_methods if method in {"tree-ring", "ring-id", "wind", "t2smark"} else advanced_methods, method.replace("-", "_"))))
                self.assertEqual(len(validated_options(config, {})), len(config["options"]))
                self.assertEqual(len(config["revision"]), 40)

    def test_registry_keeps_existing_five(self):
        registry = MethodRegistry(ROOT)
        self.assertEqual(len(registry.list_methods()), 14)
        self.assertEqual(registry.get_adapter("sfwmark").method_id, "sfwmark")
        self.assertIsInstance(registry.get_adapter("ring-id"), RepositoryMethodAdapter)

    def test_invalid_options_do_not_start_a_runner(self):
        with patch("adapters.repository_method.run_repo_script") as runner:
            for value in [float("nan"), float("inf"), True, 0, 1.5, "50"]:
                result = self.adapter.run(self.request(options={"inference_steps": value}))
                self.assertEqual(result.status, "failed")
            runner.assert_not_called()

    def test_unknown_workflow_and_variant(self):
        self.assertEqual(self.adapter.run(self.request(submethod_id="made-up")).status, "unsupported")
        self.assertEqual(self.adapter.run(self.request(workflow="detect", analysis_mode="train")).status, "unsupported")

    def test_source_is_required_and_confined(self):
        for source in [None, "../../etc", "wrong"]:
            result = self.adapter.run(self.request(workflow="detect", analysis_mode="detect", source_job_id=source))
            self.assertEqual(result.status, "failed")

    def test_source_cannot_cross_method(self):
        self.source(method="ring-id")
        result = self.adapter.run(self.request(workflow="detect", analysis_mode="detect", source_job_id="123456abcdef"))
        self.assertIn("another method", result.recovered_payload)

    def test_source_cannot_cross_variant(self):
        self.source(submethod_id="zeros")
        result = self.adapter.run(self.request(workflow="detect", analysis_mode="detect", source_job_id="123456abcdef"))
        self.assertIn("another method", result.recovered_payload)

    def test_missing_private_state_is_rejected(self):
        source = self.source()
        (source / "private.pt").unlink()
        result = self.adapter.run(self.request(workflow="detect", analysis_mode="detect", source_job_id="123456abcdef"))
        self.assertIn("state is missing", result.recovered_payload)

    def test_analysis_uses_saved_options(self):
        self.source()
        with patch("adapters.repository_method.run_repo_script", return_value="started") as runner:
            result = self.adapter.run(self.request(workflow="detect", analysis_mode="detect", source_job_id="123456abcdef",
                options={"inference_steps": 100}, image_data_url="data:image/png;base64,aGVsbG8="))
            self.assertEqual(result, "started")
            command = runner.call_args.kwargs["command"]
            payload = json.loads(Path(command[-1]).read_text())
            self.assertEqual(payload["options"]["inference_steps"], 25)
            self.assertTrue(payload["state_dir"].endswith("123456abcdef"))

    def test_upload_filename_cannot_escape_upload_folder(self):
        path = save_image_input(self.root, self.request(image_name="../../escape.png", image_data_url="data:image/png;base64,aGVsbG8="), "abc")
        self.assertEqual(path.parent, self.root / "backend/storage/uploads/abc")

    def test_no_external_image_fetch(self):
        self.assertIsNone(save_image_input(self.root, self.request(image_data_url="http://example.com/image.png"), "abc"))
        self.assertIsNone(save_image_input(self.root, self.request(image_data_url="/files/../../private.pt"), "abc"))

    def test_parameter_relationships(self):
        with self.assertRaises(ValueError):
            validated_options(CATALOG["ring-id"], {"assigned_keys": 2})
        with self.assertRaises(ValueError):
            validated_options(CATALOG["robin"], {"inference_steps": 10})
        with self.assertRaises(ValueError):
            validated_options(CATALOG["robin"], {"w_low_radius": 29, "w_up_radius": 20})
        with self.assertRaises(ValueError):
            validated_options(CATALOG["tree-ring"], {"w_channel": True})

    def test_revision_mismatch_fails_before_imports(self):
        with patch("run_job.subprocess.check_output", return_value="different"):
            with self.assertRaises(SetupRequired):
                preflight({"method": "tree-ring", "repo": "/unused"}, CATALOG)

    def test_nonfinite_score_is_valid_json_without_fake_decision(self):
        context = Context.__new__(Context)
        payload = context.metrics("uncalibrated", {"distance": math.inf})
        json.dumps(payload, allow_nan=False)
        self.assertNotIn("detected", payload["raw"])
        self.assertNotIn("detection_score", payload)

    def test_result_marker_survives_upstream_logging(self):
        self.assertEqual(_result_marker('loading\n@@RESULT@@{"status":"setup_required"}\n')["status"], "setup_required")

    def test_context_reuses_saved_model_seed_and_parameters(self):
        source = self.source()
        payload = dict(operation="detect", output_dir=str(self.root / "out"), state_dir=str(source),
                       options={"inference_steps": 100}, model_id="different-model", seed=99)
        with patch("run_job.load_trusted", return_value={}):
            context = Context(payload)
        self.assertEqual(context.model, "saved-model")
        self.assertEqual(context.options["inference_steps"], 25)
        self.assertEqual(context.request["seed"], 15)

    def test_checkpoint_change_requires_setup(self):
        from advanced_methods import bound_checkpoint
        checkpoint = self.root / "model.pth"
        checkpoint.write_bytes(b"new model")
        context = Context.__new__(Context)
        context.generate = False
        context.state = {"checkpoints": {"TEST_MODEL": "old digest"}}
        with patch("advanced_methods.checkpoint", return_value=checkpoint):
            with self.assertRaises(SetupRequired):
                bound_checkpoint(context, "TEST_MODEL")


class HttpContracts(unittest.TestCase):
    def test_missing_environment_and_private_file_protection(self):
        import threading
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        import server
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            storage = root / "backend/storage/outputs/123456abcdef"
            storage.mkdir(parents=True)
            for name in ("private.pt", "model.pth", "watermarked.png"):
                (storage / name).write_bytes(b"test")
            registry = MethodRegistry(ROOT)
            registry.project_root = root
            with patch.object(server, "PROJECT_ROOT", root), patch.object(server, "REGISTRY", registry):
                http = ThreadingHTTPServer(("127.0.0.1", 0), server.ApiHandler)
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{http.server_port}"
                try:
                    for name in ("private.pt", "model.pth"):
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(base + "/files/outputs/123456abcdef/" + name)
                        self.assertEqual(error.exception.code, 404)
                    with urllib.request.urlopen(base + "/files/outputs/123456abcdef/watermarked.png") as response:
                        self.assertEqual(response.read(), b"test")
                    body = json.dumps(dict(method="tree-ring", submethodId="ring", message="", prompt="test", seed=42)).encode()
                    request = urllib.request.Request(base + "/watermark/generate", data=body, headers={"content-type": "application/json"})
                    with urllib.request.urlopen(request) as response:
                        result = json.load(response)["result"]
                    self.assertEqual(result["status"], "setup_required")
                    self.assertIsNone(result["image_url"])
                finally:
                    http.shutdown()
                    http.server_close()
                    thread.join()


if __name__ == "__main__":
    unittest.main()
