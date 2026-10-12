"""Repository-backed workflows that also need learned or semantic model artifacts."""
import hashlib
from types import SimpleNamespace

from noise_methods import pipeline, generate, invert, tree_args
from run_job import checkpoint, load_trusted, move, SetupRequired


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bound_checkpoint(c, name):
    path = checkpoint(name)
    digest = fingerprint(path)
    if not c.generate and c.state["checkpoints"].get(name) != digest:
        raise SetupRequired(f"{name} does not match the checkpoint used for this generation job")
    return path, digest


def gaussmarker(c):
    import torch
    import joblib
    import tr_utils as tr
    from utils import transform_img, set_random_seed
    from watermark import Gaussian_Shading_chacha
    from unet.unet_model import UNet
    gnr_path, digest = bound_checkpoint(c, "WATERMARK_GAUSSMARKER_GNR")
    info = load_trusted(checkpoint("WATERMARK_GAUSSMARKER_W1")) if c.generate else move(c.state["info"], "cpu")
    wm = Gaussian_Shading_chacha(1, 8, 8, 1e-6, 1000000, watermark=info["w"], m=info["m"], key=info["key"], nonce=info["nonce"])
    pipe = pipeline(c)
    args = tree_args(c)
    model = UNet(8 if c.options["classifier_type"] else 4, 4, nf=c.options["model_nf"]).to(c.device).eval()
    model.load_state_dict(load_trusted(gnr_path))
    if c.generate:
        pattern = tr.get_watermarking_pattern(pipe, args, c.device, shape=(1, 4, 64, 64))
        mask = tr.get_watermarking_mask(pattern.real, args, c.device)
        set_random_seed(c.request["seed"])
        latent, _ = wm.create_watermark_and_return_w_m()
        latent = tr.inject_watermark(latent.float().to(c.device), mask, pattern, args)
        return c.save(generate(c, pipe, latent), {"info": info, "pattern": pattern, "mask": mask,
                       "checkpoints": {"WATERMARK_GAUSSMARKER_GNR": digest}})
    emb = pipe.get_text_embedding("")
    img = transform_img(c.image()).unsqueeze(0).to(device=c.device, dtype=emb.dtype)
    # Preserve this repository's VAE sampling behavior (its default is sample=True).
    noise = pipe.forward_diffusion(latents=pipe.get_image_latents(img), text_embeddings=emb,
                                   guidance_scale=1, num_inference_steps=c.options["inversion_steps"])
    signs = (noise > 0).float()
    m = torch.from_numpy(wm.m).reshape(1, 4, 64, 64).float().to(c.device)
    inputs = torch.cat([m, signs], dim=1) if c.options["classifier_type"] else signs
    restored = (torch.sigmoid(model(inputs)) > .5).int()
    recovered = wm.pred_w_from_m(restored)
    accuracy = float((recovered.cpu() == wm.watermark.cpu()).float().mean())
    raw_accuracy = float((wm.pred_w_from_latent(noise).cpu() == wm.watermark.cpu()).float().mean())
    _, distance = tr.eval_watermark(noise, noise, c.state["mask"], c.state["pattern"], args)
    clf = joblib.load("sd21_cls2.pkl")
    probability = float(clf.predict_proba([[accuracy, -float(distance)]])[0, 1])
    return c.metrics("Native spatial recovery, Gaussian Noise Restorer and frequency-score ensemble. Ensemble operating thresholds require calibration. Optional affine alignment is not enabled in this adapter.",
                     {"Raw bit accuracy": raw_accuracy, "Restored bit accuracy": accuracy,
                      "Fourier L1 distance": float(distance), "Ensemble probability": probability}, bit_error_rate=1-accuracy)


def seal(c):
    import torch
    from transformers import Blip2Processor, Blip2ForConditionalGeneration
    from sentence_transformers import SentenceTransformer
    from utils import generate_caption, generate_initial_noise, calculate_patch_l2, transform_img
    pipe = pipeline(c, scheduler=False)
    processor = Blip2Processor.from_pretrained("Salesforce/blip2-flan-t5-xl")
    captioner = Blip2ForConditionalGeneration.from_pretrained("Salesforce/blip2-flan-t5-xl", torch_dtype=torch.float16).to(c.device).eval()
    sentence = SentenceTransformer("kasraarabi/finetuned-caption-embedding").to(c.device).eval()
    def semantic_noise(image):
        caption = generate_caption(image, processor, captioner)
        embedding = sentence.encode(caption, convert_to_tensor=True).to(c.device)
        embedding = embedding / torch.norm(embedding)
        return generate_initial_noise(embedding, c.options["k"], c.options["b"], 42, c.device).to(pipe.vae.dtype), caption
    if c.generate:
        first = pipe(c.request["prompt"], height=512, width=512, guidance_scale=c.options["guidance_scale"],
                     num_inference_steps=c.options["inference_steps"]).images[0]
        noise, caption = semantic_noise(first)
        return c.save(generate(c, pipe, noise), {}, initial_caption=caption, semantic_seed=42)
    # Reconstruct the key from the analyzed image, not the original caption.
    expected_noise, caption = semantic_noise(c.image())
    distances = calculate_patch_l2(invert(c, pipe, transform_img), expected_noise, c.options["k"])
    return c.metrics("Content-conditioned patch distances using a fresh caption of the analyzed image. No calibrated presence threshold is applied.",
                     {"Minimum patch L2": min(distances), "Mean patch L2": sum(distances)/len(distances), "Patches": len(distances)},
                     caption=caption, patch_distances=distances)


def robin(c):
    import optim_utils as u
    pipe = pipeline(c)
    o = c.options
    args = SimpleNamespace(w_channel=o["w_channel"], w_low_radius=o["w_low_radius"], w_up_radius=o["w_up_radius"],
                           w_mask_shape="circle", w_injection="complex", w_measurement="l1_complex")
    if c.generate:
        state = load_trusted(checkpoint("WATERMARK_ROBIN_CHECKPOINT"), c.device)
        pattern, condition = state["opt_wm"], state["opt_acond"]
        latent = pipe.get_random_latents()
        mask = u.get_watermarking_mask(latent, args, c.device)
        image = pipe(c.request["prompt"], latents=latent, height=512, width=512, guidance_scale=o["guidance_scale"],
                     num_inference_steps=o["inference_steps"], watermarking_mask=mask, watermarking_steps=o["injection_step"],
                     args=args, gt_patch=pattern, lguidance=7.5, opt_acond=condition.to(pipe.get_text_embedding("").dtype)).images[0]
        return c.save(image, {"pattern": pattern, "condition": condition, "mask": mask})
    emb = pipe.get_text_embedding("")
    image = u.transform_img(c.image()).unsqueeze(0).to(device=c.device, dtype=emb.dtype)
    latent = pipe.get_image_latents(image, sample=False)
    _, intermediates, _ = pipe.forward_diffusion(latents=latent, text_embeddings=emb, guidance_scale=1,
                                                 num_inference_steps=o["inversion_steps"], latents_b=[latent])
    recovered = intermediates[o["injection_step"]]
    _, distance = u.eval_watermark(recovered, recovered, c.state["mask"], c.state["pattern"], args)
    return c.metrics("Verification at the repository's intermediate inversion step, not at the final noise. The optimized artifact must match the configured model, mask and steps.",
                     {"Intermediate step": o["injection_step"], "Fourier L1 distance": float(distance)})


def tag_wm(c):
    import torch
    import numpy as np
    from PIL import Image
    from applied_to_sd2.watermark_embedder import WatermarkEmbedder
    from utils.image_utils import transform_img
    o = c.options
    checkpoints = {}
    path = None
    if c.request["variant"] == "trainable":
        path, digest = bound_checkpoint(c, "WATERMARK_TAG_WM_DVRD")
        checkpoints["WATERMARK_TAG_WM_DVRD"] = digest
    wm = WatermarkEmbedder(wm_len=o["wm_len"], optimize_tamper_loc_method=c.request["variant"],
                           DVRD_checkpoint_path=str(path) if path else None, device=c.device)
    pipe = pipeline(c, "applied_to_sd2.inverse_stable_diffusion")
    if c.generate:
        message = torch.randint(0, 2, [o["wm_len"]], device=c.device)
        template = np.arange(4 * 64 * 64) % 2
        latent, repeated = wm.embedding_wm_tlt(message, template, latent_size=(4, 64, 64))
        # Native TAG-WM generation uses the embedder's latent dtype, without an extra cast.
        image = pipe(c.request["prompt"], latents=latent, height=512, width=512, guidance_scale=o["guidance_scale"],
                     num_inference_steps=o["inference_steps"]).images[0]
        return c.save(image, {"message": message, "template": template, "repeated": repeated, "checkpoints": checkpoints})
    noise = invert(c, pipe, lambda img: transform_img(img, target_size=(512, 512)))
    repeated, template = wm.deembedding_wm_tlt(noise)
    mask = wm.get_tamper_loc_latent(c.state["template"], template, latent_size=(4, 64, 64), tamper_confidence=o["tamper_confidence"])
    quantized = (mask.mean(dim=0, keepdim=True) >= 0).int().repeat(4, 1, 1) if "int" not in str(mask.dtype) else mask
    message = wm.calc_watermark(o["wm_len"], repeated, pred_tamper_loc_latent=quantized, with_tamper_loc=bool(o["calc_wm_use_tamper_loc"]))
    accuracy = wm.eval_watermark(c.state["message"], message)
    image_mask = wm.trans_tamper_loc_latent2img(pipe, mask, binaryize_thre=0)
    path = c.output / "tamper-mask.png"
    Image.fromarray((image_mask.permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)).save(path)
    return c.metrics("Native tamper-map refinement and tamper-aware decoding. No localization accuracy or IoU is claimed without a ground-truth edit mask.",
                     {"Bit accuracy": accuracy, "Detection threshold": wm.tau_onebit, "Traceability threshold": wm.tau_bits,
                      "Detected": accuracy >= wm.tau_onebit, "Traceable": accuracy >= wm.tau_bits},
                     payload="".join(str(int(bit)) for bit in message.cpu()), mask_path=str(path), bit_error_rate=1-accuracy)


def serum(c):
    from torchvision.transforms.functional import to_pil_image, to_tensor
    from src.utils.config import Config
    from src.models import Watermark, WatermarkScoreModel, DiffusionModel, ModelWrapper, get_vae, encode, decode
    if c.generate:
        config = Config(str(checkpoint("WATERMARK_SERUM_CONFIG")))
        watermark = Watermark.load(config, filename=str(checkpoint("WATERMARK_SERUM_WATERMARK"))).to(c.device).eval()
        detector = WatermarkScoreModel.load(config, filename=str(checkpoint("WATERMARK_SERUM_DETECTOR"))).to(c.device).eval()
    else:
        # Keep the complete generation configuration, independent of later environment changes.
        config = Config.__new__(Config)
        config._raw = c.state["config"]
        config._parse()
        detector = WatermarkScoreModel(config).to(c.device).eval()
        detector.load_state_dict(c.state["detector"])
    if (config.shapes.latent_channels, config.shapes.latent_height, config.shapes.latent_width) != (4, 64, 64) or tuple(config.evaluation.size or ()) != (512, 512):
        raise SetupRequired("The published SERUM score model requires 4x64x64 latents. Supply its matching 512px model configuration.")
    get_vae(config)
    if c.generate:
        model = ModelWrapper(DiffusionModel(config).requires_grad_(False).eval().to(c.device))
        noise, _ = watermark(1, ret_noise=True)
        latent = model.generate_full(batch_size=1, noise=noise.half(), x_ts_ret=False,
                                     positive_prompts=[c.request["prompt"]], negative_prompts=[""])
        image = to_pil_image(((decode(latent)[0].cpu().float() + 1) / 2).clamp(0, 1))
        # Preserve the native evaluation export's crop/resize operation.
        from src.evaluation.generate import save_image
        from PIL import Image
        save_image(config, image, str(c.output / "watermarked.png"))
        with Image.open(c.output / "watermarked.png") as processed:
            image = processed.copy()
        c.request["model_id"] = config.diffusion.stable_diffusion_model_id
        return c.save(image, {"config": config._raw, "detector": detector.state_dict()})
    image = c.image()
    if image.size != (512, 512):
        raise ValueError("SERUM analysis requires a 512x512 image for its fixed-size latent detector")
    latent = encode((to_tensor(image).unsqueeze(0).to(c.device) * 2 - 1).float())
    score = float(detector(latent.float()).item())
    return c.metrics("VAE encoding followed by the trained latent score model; no diffusion inversion. The sigmoid score is not a calibrated presence decision.", {"Detector score": score})
