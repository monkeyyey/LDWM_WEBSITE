"""Optional native math checks with a stand-in image pipeline, NOT diffusion tests."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/integrations/repository_methods"))
import noise_methods
from run_job import Context

CATALOG = json.loads((ROOT / "backend/config/repository_methods.json").read_text())


def upstream(method):
    spec = CATALOG[method]
    return Path(os.environ.get(spec["repo_env"], ROOT / "work/review" / Path(spec["repo_path"]).name))


def native(path):
    spec = importlib.util.spec_from_file_location("native_math", path)
    module = importlib.util.module_from_spec(spec)
    # Dataset loading isn't used by these math helpers.
    with patch.dict(sys.modules, {"datasets": SimpleNamespace(load_dataset=lambda *a, **kw: None)}):
        spec.loader.exec_module(module)
    return module


class MathContext(Context):
    def __init__(self, method, variant=None):
        spec = CATALOG[method]
        self.options = {key: value["default"] for key, value in spec["options"].items()}
        self.options.update(assigned_keys=4, key_index=1, noise_count=8)
        self.request = dict(method=method, variant=variant or spec["variants"][0], operation="generate", prompt="test", seed=42)
        self.device = "cpu"
        self.generate = True
        self.state = {}

    def save(self, image, state, **metadata):
        self.state = state
        return {"saved": True}

    def image(self):
        return Image.new("RGB", (512, 512))

    def analyze(self, operation):
        self.generate = False
        self.request["operation"] = operation


class StandInPipe:
    device = "cpu"
    unet = SimpleNamespace(dtype=torch.float32)
    vae = SimpleNamespace(dtype=torch.float32)

    def __init__(self, tuple_output=False):
        self.tuple_output = tuple_output
        self.noise = None

    def get_random_latents(self):
        return torch.randn(1, 4, 64, 64)

    def get_text_embedding(self, prompt):
        return torch.zeros(1)

    def encode_prompt(self, *args):
        return (torch.zeros(1),)

    def __call__(self, prompt, latents, **kwargs):
        self.noise = latents.float().clone()
        output = SimpleNamespace(images=[Image.new("RGB", (512, 512))])
        return (output, None) if self.tuple_output else output

    def get_image_latents(self, image, sample=False):
        assert sample is False
        return self.noise.clone()

    def forward_diffusion(self, **kwargs):
        assert kwargs["guidance_scale"] == 1
        return self.noise.clone()

    naive_forward_diffusion = forward_diffusion


class NativeMathTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        random.seed(42)
        np.random.seed(42)

    def test_tree_ring_patterns_and_scores(self):
        u = native(upstream("tree-ring") / "optim_utils.py")
        for variant in ("ring", "rand", "zeros"):
            with self.subTest(variant=variant):
                c, pipe = MathContext("tree-ring", variant), StandInPipe()
                with patch.dict(sys.modules, {"optim_utils": u}), patch.object(noise_methods, "pipeline", return_value=pipe):
                    noise_methods.tree_ring(c)
                    self.assertEqual(c.state["mask"].shape, (1, 4, 64, 64))
                    c.analyze("detect")
                    result = noise_methods.tree_ring(c)
                    distance = result["raw"]["metrics"][0]["value"]
                    _, expected = u.eval_watermark(pipe.noise, pipe.noise, c.state["mask"], c.state["pattern"], noise_methods.tree_args(c))
                    self.assertAlmostEqual(distance, float(expected), places=5)
                    pipe.noise = torch.randn_like(pipe.noise)
                    negative = noise_methods.tree_ring(c)["raw"]["metrics"][0]["value"]
                    # Native real projection means even ideal recovery need not
                    # have zero distance, unlike Ring-ID's corrected pattern.
                    self.assertLess(distance, negative)
                    self.assertNotIn("detected", result["raw"])

    def test_ring_id_searches_bank_not_ground_truth(self):
        u = native(upstream("ring-id") / "utils.py")
        c, pipe = MathContext("ring-id"), StandInPipe()
        with patch.dict(sys.modules, {"utils": u}), patch.object(noise_methods, "pipeline", return_value=pipe):
            noise_methods.ring_id(c)
            self.assertEqual(len(c.state["bank"]), 4)
            c.analyze("identify")
            result = noise_methods.ring_id(c)
            self.assertEqual(result["raw"]["predicted_index"], 1)
            self.assertTrue(result["raw"]["identified"])
            c.state["index"] = 3
            result = noise_methods.ring_id(c)
            self.assertEqual(result["raw"]["predicted_index"], 1)
            self.assertFalse(result["raw"]["identified"])
            c.analyze("verify")
            wrong = noise_methods.ring_id(c)["raw"]["metrics"][1]["value"]
            c.state["index"] = 1
            right = noise_methods.ring_id(c)["raw"]["metrics"][1]["value"]
            self.assertLess(right, wrong)

    def test_t2s_native_two_stage_roundtrip_and_corrupted_session(self):
        t2s = native(upstream("t2smark") / "src/t2s.py")
        c, pipe = MathContext("t2smark"), StandInPipe(tuple_output=True)
        imports = {"src": ModuleType("src"), "src.t2s": t2s,
                   "src.utils": SimpleNamespace(to_tensor=lambda image: torch.zeros(1, 3, 512, 512))}
        # Only bypass hard-coded CUDA transfers to exercise native math on CPU.
        with patch.dict(sys.modules, imports), patch.object(torch.Tensor, "cuda", lambda self, *a, **kw: self), patch.object(noise_methods, "pipeline", return_value=pipe):
            noise_methods.t2smark(c)
            c.analyze("decode")
            result = noise_methods.t2smark(c)
            self.assertEqual(result["raw"]["bit_error_rate"], 0)
            self.assertEqual(len(result["recovered_payload"]), c.options["msg_length"])
            # Corrupt only the key channel. Message recovery must now fail, even
            # though the untouched ground-truth session is still in saved state.
            pipe.noise[:, c.options["key_channel_idx"]] *= -1
            result = noise_methods.t2smark(c)
            self.assertGreater(result["raw"]["bit_error_rate"], .2)

    def test_wind_native_full_fallback_and_fast_registry(self):
        u = native(upstream("wind") / "utils.py")
        wandb = SimpleNamespace(init=lambda **kw: None, log=lambda *a, **kw: None)
        for variant in ("full", "fast"):
            path = upstream("wind") / f"WIND_{variant}.py"
            node = next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.ClassDef) and node.name == "WatermarkClass")
            module = ModuleType(f"WIND_{variant}")
            vars(module).update(vars(u))
            vars(module).update(torch=torch, random=random, hashlib=hashlib, time=time, transforms=transforms, F=torch.nn.functional, wandb=wandb)
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), vars(module))
            c, pipe = MathContext("wind", variant), StandInPipe()
            original_randn = torch.randn
            def cpu_randn(*args, **kwargs):
                # CPU FFT has no half support; keep the algorithm unchanged.
                if kwargs.get("dtype") == torch.float16:
                    kwargs["dtype"] = torch.float32
                return original_randn(*args, **kwargs)
            with patch.dict(sys.modules, {"utils": u, f"WIND_{variant}": module, "wandb": wandb}), patch.object(noise_methods, "pipeline", return_value=pipe), patch.object(torch, "randn", cpu_randn):
                noise_methods.wind(c)
                c.analyze("identify")
                result = noise_methods.wind(c)
                values = {m["label"]: m["value"] for m in result["raw"]["metrics"]}
                self.assertTrue(values["Identification correct"])
                self.assertEqual(values["Registered noises"], 8 if variant == "full" else 1)
                if variant == "full":
                    pipe.noise *= 10
                    result = noise_methods.wind(c)
                    values = {m["label"]: m["value"] for m in result["raw"]["metrics"]}
                    self.assertTrue(values["Fallback used"])


if __name__ == "__main__":
    unittest.main()
