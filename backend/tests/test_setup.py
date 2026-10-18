"""Setup contracts that run without CUDA, network access or checkpoint loading."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from environment import load_environment, read_environment

spec = importlib.util.spec_from_file_location("ldwm_setup", ROOT / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class EnvironmentTests(unittest.TestCase):
    def test_paths_spaces_and_exported_precedence_without_shell_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "env"
            path.write_text('BASE="/a folder"\nNEXT="${BASE}/file"\nLITERAL="$(touch sentinel)"\n')
            values = read_environment(path, {"BASE": "/external"})
            self.assertEqual(values["NEXT"], "/external/file")
            self.assertEqual(values["LITERAL"], "$(touch sentinel)")
            self.assertFalse((path.parent / "sentinel").exists())
            with patch.dict(os.environ, {"BASE": "/external"}, clear=True):
                load_environment(path)
                self.assertEqual(os.environ["BASE"], "/external")

    def test_bad_assignment_does_not_echo_secret_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "env"
            path.write_text("NOT AN ASSIGNMENT private-token\n")
            with self.assertRaises(ValueError) as error:
                read_environment(path)
            self.assertNotIn("private-token", str(error.exception))


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in (("ROOT", self.root), ("ENV_FILE", self.root / ".env.gpu")):
            patcher = patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_config_round_trip_preserves_custom_values_and_backs_up_changes(self):
        original = {"WATERMARK_TREE_RING_PYTHON": "/custom/python", "CUSTOM": "/a folder/caf\u00e9"}
        setup.write_environment(original)
        values = setup.defaults(original, ["tree-ring"])
        self.assertEqual(values["WATERMARK_TREE_RING_PYTHON"], "/custom/python")
        setup.write_environment(values)
        self.assertEqual(read_environment(setup.ENV_FILE)["CUSTOM"], original["CUSTOM"])
        self.assertEqual(len(list(self.root.glob(".env.gpu.bak.*"))), 1)
        self.assertEqual(setup.ENV_FILE.stat().st_mode & 0o777, 0o600)
        setup.write_environment(values)
        self.assertEqual(len(list(self.root.glob(".env.gpu.bak.*"))), 1)

    def test_exported_model_override_is_preserved_without_an_env_file(self):
        with patch.dict(os.environ, {"WATERMARK_TREE_RING_MODEL_ID": "custom-model", "WATERMARK_TREE_RING_MODEL_REVISION": "custom-ref"}, clear=True):
            values = setup.defaults(setup.configured_values(), ["tree-ring"])
        self.assertEqual(values["WATERMARK_TREE_RING_MODEL_ID"], "custom-model")
        self.assertEqual(values["WATERMARK_TREE_RING_MODEL_REVISION"], "custom-ref")

    def test_bundle_can_move_to_another_machine_and_detects_changed_files(self):
        checkpoint = self.root / "trained.pt"
        checkpoint.write_bytes(b"opaque checkpoint; never unpickle in setup")
        bundle = self.root / "bundle"
        setup.export_artifacts(bundle, {"WATERMARK_ROBIN_CHECKPOINT": str(checkpoint)}, ["robin"])
        relocated = self.root / "relocated"
        bundle.rename(relocated)
        values = setup.import_artifacts(relocated, ["robin"])
        imported = Path(values["WATERMARK_ROBIN_CHECKPOINT"])
        self.assertEqual(imported.read_bytes(), checkpoint.read_bytes())
        imported.write_bytes(b"changed")
        with self.assertRaisesRegex(setup.SetupError, "Checksum mismatch"):
            setup.import_artifacts(relocated, ["robin"])

    def test_bundle_cannot_reference_files_outside_it(self):
        outside = self.root / "outside.pt"
        outside.write_bytes(b"outside")
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1, "files": {
            "WATERMARK_ROBIN_CHECKPOINT": {"path": "../outside.pt", "sha256": setup.sha256(outside)}
        }}))
        with self.assertRaisesRegex(setup.SetupError, "invalid bundled file"):
            setup.import_artifacts(bundle, ["robin"])

    def test_bundle_revision_must_match_the_method(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1, "revisions": {"robin": "different"}, "files": {}}))
        with self.assertRaisesRegex(setup.SetupError, "source revision"):
            setup.import_artifacts(bundle, ["robin"])

    def test_export_never_overwrites_existing_files(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "keep").write_text("user data")
        with self.assertRaisesRegex(setup.SetupError, "preserved"):
            setup.export_artifacts(bundle, {}, ["tree-ring"])
        self.assertEqual((bundle / "keep").read_text(), "user data")

    def test_all_methods_have_pinned_sources_and_installable_profiles(self):
        self.assertEqual(len(setup.METHODS), 14)
        for method, config in setup.METHODS.items():
            with self.subTest(method=method):
                self.assertEqual(len(config["revision"]), 40)
                profile = "wind" if config["profile"] == "seal" else config["profile"]
                runtime = setup.PROFILES[profile]
                requirements = setup.REQUIREMENTS / runtime.get("requirements", profile + ".txt")
                self.assertTrue(requirements.is_file())

    def test_profile_installs_the_cuda_wheel_and_bootstraps_pyldpc(self):
        with patch.object(setup, "run") as run:
            setup.install_profile("uv", "gaussian-shannon")
        calls = [list(map(str, call.args[0])) for call in run.call_args_list]
        self.assertTrue(any("https://download.pytorch.org/whl/cu124" in call for call in calls))
        self.assertTrue(any("--no-build-isolation" in call and "pyldpc==0.7.9" in call for call in calls))
        self.assertTrue(any("check" in call for call in calls))

    def test_preview_makes_no_files_or_network_calls(self):
        with patch.object(sys, "argv", ["setup", "--methods", "tree-ring,ring-id", "--plan"]), patch.object(setup, "run") as run:
            self.assertEqual(setup.main(), 0)
            run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_linux_install_shares_legacy_runtime_and_reports_incomplete_setup(self):
        with patch.object(sys, "argv", ["setup", "--methods", "tree-ring,ring-id"]), \
             patch.object(setup, "configured_values", return_value={"LDWM_BACKEND_PYTHON": sys.executable}), \
             patch.object(setup.platform, "system", return_value="Linux"), \
             patch.object(setup.platform, "machine", return_value="x86_64"), \
             patch.object(setup.os, "geteuid", return_value=1000), \
             patch.object(setup.shutil, "which", return_value="/tools/executable"), \
             patch.object(setup, "ensure_uv", return_value="uv"), \
             patch.object(setup, "ensure_node", return_value="/tools/node/bin"), \
             patch.object(setup, "run") as run, \
             patch.object(setup, "install_profile") as install, \
             patch.object(setup, "check", return_value=False):
            self.assertEqual(setup.main(), 2)
        install.assert_called_once_with("uv", "legacy")
        values = read_environment(setup.ENV_FILE)
        self.assertEqual(values["WATERMARK_TREE_RING_PYTHON"], values["WATERMARK_RING_ID_PYTHON"])
        self.assertEqual(values["PYTHONDONTWRITEBYTECODE"], "1")
        commands = [list(map(str, call.args[0])) for call in run.call_args_list]
        self.assertTrue(any("--clone" in command for command in commands))
        self.assertFalse(any("train" in " ".join(command) for command in commands))

    def test_sfw_model_override_leaves_upstream_source_unchanged(self):
        source = self.root / "generate.py"
        text = 'model_id = "old-model"\nprint(model_id)\n'
        source.write_text(text)
        result = subprocess.run([sys.executable, ROOT / "backend/integrations/sfwmark/execute_generate.py"],
                                cwd=self.root, env={**os.environ, "SFW_MODEL_ID": "configured-model"}, text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.strip(), "configured-model")
        self.assertEqual(source.read_text(), text)


if __name__ == "__main__":
    unittest.main()
