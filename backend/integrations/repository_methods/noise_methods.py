"""Single-image entry points adapted from the upstream generation/evaluation loops."""
import importlib
import itertools
import os
import random
from types import SimpleNamespace


def pipeline_revision(c):
    method = c.request["method"].upper().replace("-", "_")
    return os.environ.get(f"WATERMARK_{method}_MODEL_REVISION", "main")


def pipeline(c, module="inverse_stable_diffusion", scheduler=True):
    import torch
    kwargs = {"torch_dtype": torch.float16, "revision": pipeline_revision(c)}
    if scheduler:
        from diffusers import DPMSolverMultistepScheduler
        kwargs["scheduler"] = DPMSolverMultistepScheduler.from_pretrained(c.model, subfolder="scheduler")
    pipe = importlib.import_module(module).InversableStableDiffusionPipeline.from_pretrained(c.model, **kwargs)
    return pipe.to(c.device)


def generate(c, pipe, latents):
    import torch
    return pipe(c.request["prompt"], latents=latents.to(dtype=torch.float16), height=512, width=512,
                guidance_scale=c.options["guidance_scale"], num_inference_steps=c.options["inference_steps"]).images[0]


def invert(c, pipe, transform):
    emb = pipe.get_text_embedding("")
    image = transform(c.image()).unsqueeze(0).to(device=c.device, dtype=emb.dtype)
    latent = pipe.get_image_latents(image, sample=False)
    return pipe.forward_diffusion(latents=latent, text_embeddings=emb, guidance_scale=1,
                                  num_inference_steps=c.options["inversion_steps"])


def tree_args(c):
    return SimpleNamespace(w_seed=c.options.get("w_seed", 999999), w_channel=c.options.get("w_channel", 3),
                           w_pattern=c.request["variant"] if c.request["method"] == "tree-ring" else "ring",
                           w_mask_shape="circle", w_radius=c.options.get("w_radius", 10),
                           w_measurement="l1_complex", w_injection="complex", w_pattern_const=0)


def tree_ring(c):
    import optim_utils as u
    pipe = pipeline(c)
    args = tree_args(c)
    if c.generate:
        pattern = u.get_watermarking_pattern(pipe, args, c.device)
        u.set_random_seed(c.request["seed"])
        latent = pipe.get_random_latents()
        mask = u.get_watermarking_mask(latent, args, c.device)
        image = generate(c, pipe, u.inject_watermark(latent, mask, pattern, args))
        return c.save(image, {"pattern": pattern, "mask": mask})
    reversed_noise = invert(c, pipe, u.transform_img)
    _, distance = u.eval_watermark(reversed_noise, reversed_noise, c.state["mask"], c.state["pattern"], args)
    return c.metrics("Fourier L1 distance (lower is closer). A calibrated negative-image dataset is needed for a detection threshold.", {"Fourier L1 distance": float(distance)})


def ring_bank(c, pipe):
    import torch
    import utils as u
    base = pipe.get_random_latents().to(torch.float64)
    single = torch.tensor(u.ring_mask(size=base.shape[-1], r_out=u.RADIUS, r_in=u.RADIUS_CUTOFF))
    heter = single.unsqueeze(0).repeat(len(u.HETER_WATERMARK_CHANNEL), 1, 1).to(c.device)
    mask = single.unsqueeze(0).repeat(len(u.WATERMARK_CHANNEL), 1, 1).to(c.device)
    levels = [-c.options["ring_value_range"], c.options["ring_value_range"]]
    slots = list(itertools.product(levels, repeat=len(u.RING_WATERMARK_CHANNEL)))
    combinations = list(itertools.product(slots, repeat=u.RADIUS - u.RADIUS_CUTOFF))
    if c.options["assigned_keys"] < len(combinations):
        combinations = random.sample(combinations, c.options["assigned_keys"])
    bank = [u.make_Fourier_ringid_pattern(c.device, list(combo), base, radius=u.RADIUS, radius_cutoff=u.RADIUS_CUTOFF,
                                         ring_watermark_channel=u.RING_WATERMARK_CHANNEL,
                                         heter_watermark_channel=u.HETER_WATERMARK_CHANNEL,
                                         heter_watermark_region_mask=heter) for combo in combinations]
    if c.options["fix_gt"]:
        bank = [u.fft(u.ifft(pattern).real) for pattern in bank]
    if c.options["time_shift"]:
        for pattern in bank:
            pattern[:, u.RING_WATERMARK_CHANNEL] = u.fft(torch.fft.fftshift(u.ifft(pattern[:, u.RING_WATERMARK_CHANNEL]), dim=(-1, -2)))
    return bank, mask


def ring_id(c):
    import utils as u
    pipe = pipeline(c)
    if c.generate:
        bank, mask = ring_bank(c, pipe)
        index = c.options["key_index"]
        u.set_random_seed(c.request["seed"])
        latent = u.generate_Fourier_watermark_latents(device=c.device, radius=u.RADIUS, radius_cutoff=u.RADIUS_CUTOFF,
            original_latents=pipe.get_random_latents(), watermark_pattern=bank[index],
            watermark_channel=u.WATERMARK_CHANNEL, watermark_region_mask=mask)
        return c.save(generate(c, pipe, latent), {"bank": bank, "mask": mask, "index": index})
    reversed_fft = u.fft(invert(c, pipe, u.transform_img))
    bank, mask, expected = c.state["bank"], c.state["mask"], c.state["index"]
    def distance(pattern):
        return float(u.get_distance(pattern, reversed_fft, mask, p=1, mode="complex",
                                    channel_min=c.options["channel_min"], channel=u.WATERMARK_CHANNEL))
    if c.request["operation"] == "verify":
        return c.metrics("Distance against the linked key; a calibrated threshold is required for presence detection.",
                         {"Expected pattern": expected, "Fourier L1 distance": distance(bank[expected])})
    distances = [distance(pattern) for pattern in bank]
    predicted = min(range(len(distances)), key=distances.__getitem__)
    return c.metrics("Nearest candidate across the saved pattern bank. Correct identification is not a calibrated presence decision.",
                     {"Predicted pattern": predicted, "Expected pattern": expected, "Identification correct": predicted == expected,
                      "Closest distance": distances[predicted], "Candidate patterns": len(bank)},
                     predicted_index=predicted, identified=predicted == expected)


def wind(c):
    import wandb
    wandb.init(mode="disabled")
    module = importlib.import_module("WIND_full" if c.request["variant"] == "full" else "WIND_fast")
    pipe = pipeline(c)
    if c.generate:
        bank, mask = ring_bank(c, pipe)
        args = SimpleNamespace(general_seed=c.request["seed"], num_inference_steps=c.options["inference_steps"],
                               test_num_inference_steps=c.options["inversion_steps"], channel_min=c.options["channel_min"])
        wm = module.WatermarkClass(args, c.device, c.options["noise_count"], len(bank), bank, mask, pipe)
        image, group, identity, _ = wm.encode_and_generate(pipe, c.request["prompt"], 0)
        state = {k: v for k, v in vars(wm).items() if k not in {"text_embeddings", "device", "noises", "args"}}
        state["args"] = vars(args)
        return c.save(image, {"wm": state, "group": group, "identity": identity})
    # Restore the exact native registry; do not regenerate keys or omit the full search fallback.
    wm = module.WatermarkClass.__new__(module.WatermarkClass)
    vars(wm).update(c.state["wm"])
    wm.args = SimpleNamespace(**wm.args)
    wm.device = c.device
    wm.text_embeddings = pipe.get_text_embedding("")
    group, identity, distance, _ = wm.detect_and_evaluate(pipe, c.image())
    count = wm.M if c.request["variant"] == "full" else len(wm.watermarked_latents)
    return c.metrics("Native grouped-noise search. Full mode preserves rotation search and sliding-window fallback. Fast mode searches only this job's registered noise, not the entire possible noise space.",
                     {"Predicted group": group, "Predicted noise": identity, "Expected noise": c.state["identity"],
                      "Identification correct": group == c.state["group"] and identity == c.state["identity"],
                      "First-stage L2 distance": float(distance), "Registered noises": count,
                      "Fallback used": bool(getattr(wm, "second_stage_count", 0))})


def t2smark(c):
    import torch
    from src.t2s import T2SMark
    from src.utils import to_tensor
    o = c.options
    key_encoder = T2SMark(o["key_length"], o["tau"], (1, 64, 64))
    msg_encoder = T2SMark(o["msg_length"], o["tau"], (3, 64, 64))
    pipe = pipeline(c, "src.inversion.inverse_stable_diffusion", scheduler=False)
    key_channel = o["key_channel_idx"]
    msg_channels = [i for i in range(4) if i != key_channel]
    if c.generate:
        master = torch.randint(0, 2, (o["key_length"],))
        session = torch.randint(0, 2, (o["key_length"],))
        message = torch.randint(0, 2, (o["msg_length"],))
        latent = torch.zeros(1, 4, 64, 64, device=c.device)
        latent[:, key_channel] = key_encoder.encode(session, master)
        latent[:, msg_channels] = msg_encoder.encode(message, session)
        output = pipe(c.request["prompt"], latents=latent.half(), height=512, width=512,
                      guidance_scale=o["guidance_scale"], num_inference_steps=o["inference_steps"])
        return c.save(output[0].images[0], {"master": master, "session": session, "message": message})
    emb = pipe.encode_prompt("", c.device, 1, False, None)[0]
    image_latent = pipe.get_image_latents(to_tensor(c.image()).to(c.device).half(), sample=False)
    noise = pipe.naive_forward_diffusion(latents=image_latent, text_embeddings=emb.half(), guidance_scale=1,
                                         num_inference_steps=o["inversion_steps"])
    session, statistic = key_encoder.decode(noise[0, key_channel], c.state["master"], detection=True)
    # Decoding must use the recovered session key, never the ground-truth session key.
    message = msg_encoder.decode(noise[0, msg_channels], session)
    accuracy = float((message == c.state["message"]).float().mean())
    payload = "".join(str(int(bit)) for bit in message.cpu()) if c.request["operation"] == "decode" else "--"
    return c.metrics("Two-stage decoding using the recovered session key. Detection uses the native L1 statistic; no threshold is asserted without calibration.",
                     {"Key L1 statistic": statistic, "Session-key accuracy": float((session == c.state["session"]).float().mean()),
                      "Message bit accuracy": accuracy, "Message bits": len(message)}, payload=payload, bit_error_rate=1-accuracy)
