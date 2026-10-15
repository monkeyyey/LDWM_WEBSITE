# Watermark UI and Adapter Audit

Source review: 2026-10-13. Scope: all 14 website methods, all 21 selectable
variants, generation/analysis graphs, input/output contracts, payloads, defaults,
and the boundary between website inference and upstream research workflows.

This is a source-level comparison of official Git checkouts with the local
adapters, not a claim that every model has passed GPU inference or reproduced
paper metrics. The nine repository integrations enforce their pinned source
revisions. The original five use configured checkouts; the links below record
the revisions reviewed, not a new pin enforced by those adapters.

## Categories

These are navigation groups by primary integration mechanism, not mutually
exclusive scientific classifications:

| Category | Methods | Rationale |
| --- | --- | --- |
| Latent / Initial Noise | SFWMark, Gaussian Shannon, Gaussian Shading, PRC-Watermark, Tree-Ring, Ring-ID, WIND, T2SMark | Fourier patterns, coding or noise identities in initial latents. |
| VAE / Decoder | LaWa | Modified generative VAE decoder embeds the message; a separate network extracts it. |
| Dual Domain / Semantic | GaussMarker, SEAL | Spatial-plus-Fourier signal fusion, or content-derived noise keys. |
| Optimization / Tamper Aware | ROBIN, TAG-WM | Offline-optimized intermediate injection, or joint message/localization signals. |
| Learned Detector | SERUM | Initial-noise marking with a learned detector on VAE latents, not inversion. |

## Reviewed Sources and Contracts

Each link is commit-specific. Related utility and pipeline code in the same
checkout was inspected alongside the entry points.

| Method / variants | Official source | Website behavior and important limits |
| --- | --- | --- |
| SFWMark: HSQR, HSTR | [src/generate.py](https://github.com/thomas11809/SFWMark/blob/78666128b44614a0cc471993649e3132d5dddfcb/src/generate.py), [src/utils.py](https://github.com/thomas11809/SFWMark/blob/78666128b44614a0cc471993649e3132d5dddfcb/src/utils.py) | HSQR uses QR sign patterns on channel 3; HSTR uses Hermitian rings plus heterogeneous marking. Both use the 44x44 latent center and a 2048-pattern bank. Single-image generation fixes seed 42. Verification returns known-pattern L1, not a binary decision; identification returns the nearest bank index and correctness against a stored label. The shared analysis runner computes both distances. |
| Gaussian Shannon: Gaussian, LDPC | [ldpc.py](https://github.com/Rambo-Yi/Gaussian-Shannon/blob/ad89a75bc92001777637c6cc242a31188934e082/ldpc.py) | User supplies 256 bits. Gaussian uses 64 copies and majority vote; LDPC uses rate 0.25, 16 copies and BP, followed by vote-and-retry if all per-copy parity checks fail. LDPC requires the linked H/G matrices; Gaussian does not require a source job. Inversion in the adapter uses VAE mean, prompt `man`, guidance 1 and 50 steps. Metrics are bit accuracy/BER, not candidate identification. |
| LaWa: 48-bit | [inference_AIGC.py](https://github.com/vbdi/LaWa/blob/251ac11aa223e6ff12553364a65a75add5b1aecf/inference_AIGC.py), [inference config](https://github.com/vbdi/LaWa/blob/251ac11aa223e6ff12553364a65a75add5b1aecf/configs/SD14_LaWa_inference.yaml) | The 48-bit message is user-supplied, not pretrained. Generation modifies VAE decoding; extraction calls the separate `MessageDecoder` at `model.decoder`, without inversion. A linked job is optional. The website uses the SD1.4 checkpoint/config path, not every upstream experiment. |
| Gaussian Shading: ChaCha20, Simple XOR | [run_gaussian_shading.py](https://github.com/bsmhmmlf/Gaussian-Shading/blob/09c678fadc7545acf7be12647ddf2a5e66f6a9dc/run_gaussian_shading.py), [watermark.py](https://github.com/bsmhmmlf/Gaussian-Shading/blob/09c678fadc7545acf7be12647ddf2a5e66f6a9dc/watermark.py) | Generated random bits, repetition, encryption/XOR and truncated-Gaussian sampling. Capacity varies with copy factors, default 256 bits. Linked key/state is required for inversion, decryption, voting and comparison. Detection and traceability are separate bit-accuracy threshold tests; traceability is not a candidate-bank search. The README qualifies the Simple XOR distribution guarantee. |
| PRC-Watermark: PRC | [encode.py](https://github.com/XuandongZhao/PRC-Watermark/blob/3f372c1d9cafcd0732331c0d00f0430ee822a389/encode.py), [decode.py](https://github.com/XuandongZhao/PRC-Watermark/blob/3f372c1d9cafcd0732331c0d00f0430ee822a389/decode.py) | Generate keys, call Encode without a user message, map a 16384-symbol codeword to pseudogaussian noise. Analysis computes inversion/posteriors internally; users supply an image and linked job, not posterior vectors. Detect is a statistical boolean; Decode is BP/test-bit validity. The website runs these separately, not the upstream optional OR-combined result. |
| Tree-Ring: ring, rand, zeros | [run_tree_ring_watermark.py](https://github.com/YuxinWenRick/tree-ring-watermark/blob/3015283d9cf82e90b628f02ad2121bd37408ca9a/run_tree_ring_watermark.py), [optim_utils.py](https://github.com/YuxinWenRick/tree-ring-watermark/blob/3015283d9cf82e90b628f02ad2121bd37408ca9a/optim_utils.py) | Different coefficient constructions, not three ring-pattern labels. Circular complex insertion into initial noise; linked saved mask/pattern; empty-prompt inversion; complex L1 only. Other mask/injection experiments, p-values and ROC sweeps are not website actions. |
| Ring-ID: ring-id | [identify.py](https://github.com/showlab/RingID/blob/45631a59aecd7d63ccdb640aaaf3e616fdb89fb9/identify.py), [verify.py](https://github.com/showlab/RingID/blob/45631a59aecd7d63ccdb640aaaf3e616fdb89fb9/verify.py) | Heterogeneous channel 0, binary rings on channel 3, radii 3..14; optional real-projection correction and time shift. Saves bank/mask/index. Verification compares one expected pattern; identification searches all saved candidates. The index is a job-bank label, not an account identity. No presence threshold is applied. |
| WIND: full, fast | [WIND_full.py](https://github.com/Kasraarabi/Hidden-in-the-Noise/blob/e923df7f74c7e41745c071d831e4b76d04665a5a/WIND_full.py), [WIND_fast.py](https://github.com/Kasraarabi/Hidden-in-the-Noise/blob/e923df7f74c7e41745c071d831e4b76d04665a5a/WIND_fast.py) | Full precomputes M noises, retrieves a Fourier group, performs rotation-aware matching and can fall back to global sliding-window cosine matching. Fast generates on demand; this adapter registers only one noise per job. M is not Fast's saved registry size. Returned L2 is the first-stage distance even when fallback is used. |
| T2SMark: sd21 | [option.py](https://github.com/0xD009/T2SMark/blob/0c1fbfd50fcd1fba135477a2c016e284d5d7914d/option.py), [run.py](https://github.com/0xD009/T2SMark/blob/0c1fbfd50fcd1fba135477a2c016e284d5d7914d/run.py) | Per-job random master/session/message; key in one channel, message in the remaining three. Both analysis actions perform naive inversion, recover the session key and decode using that recovered key. Detect returns the L1 statistic and recovery metrics, not a boolean; Decode also exposes bits. SD3.5 and fixed-key experiments are not integrated. |
| GaussMarker: chacha | [gaussmarker_gen.py](https://github.com/SunnierLee/GaussMarker/blob/4ac9bfd4e152a56bd93c2a06a809ef6ff8e73155/gaussmarker_gen.py), [gaussmarker_det.py](https://github.com/SunnierLee/GaussMarker/blob/4ac9bfd4e152a56bd93c2a06a809ef6ff8e73155/gaussmarker_det.py) | Matching W1 and GNR artifacts are required, including during generation. The spatial branch restores signs with GNR then decrypts/votes; the Fourier branch compares original inverted noise. Released `sd21_cls2.pkl` combines restored bit accuracy and negative Fourier distance. Returns accuracies, BER, distance and ensemble probability, without an app threshold. No affine alignment or restorer training is run in the website. |
| SEAL: seal | [SEAL.py](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/SEAL.py), [utils.py](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/utils.py) | Preliminary image -> BLIP-2 caption -> sentence embedding -> SimHash patch keys -> second generation. Verification recaptions the analyzed image and compares expected semantic noise with inverted noise. Linked job restores configuration, not an original secret caption. Returns patch L2 statistics, caption and distances; no calibrated presence decision or localization mask. |
| ROBIN: robin | [inject_wm_inner_latent_robin.py](https://github.com/Hannah1102/ROBIN/blob/6b2c2ddf5e50d7d75c71a41c84a7781d2826be1f/inject_wm_inner_latent_robin.py), [gen_watermark.py](https://github.com/Hannah1102/ROBIN/blob/6b2c2ddf5e50d7d75c71a41c84a7781d2826be1f/gen_watermark.py) | Loads `opt_wm` and `opt_acond`, inserts at an intermediate step and uses learned hiding conditioning. Verification measures Fourier L1 at the configured intermediate inversion index. Optimization is offline and artifacts must match the model/mask/schedule. No thresholded verification result. |
| TAG-WM: trainable, trainfree | [applied_to_sd2/test.py](https://github.com/Suchenl/TAG-WM/blob/74890e38211a986aebda95c4c3dd160578632977/applied_to_sd2/test.py), [watermark_embedder.py](https://github.com/Suchenl/TAG-WM/blob/74890e38211a986aebda95c4c3dd160578632977/applied_to_sd2/watermark_embedder.py) | Joint random message/fixed alternating localization template. Trainable loads a fingerprint-bound DVRD checkpoint (also during generation); trainfree uses adaptive checkpoint-free refinement. Decode and Localize both run inversion, template comparison, refinement and optional tamper-aware voting; both return bits, BER, decisions and mask. No IoU without a true edit mask. Fixed encryption/shuffle seeds are research defaults, not per-user secrets. |
| SERUM: serum | [src/training/train.py](https://github.com/Hubizon/SERUM/blob/02f4929e30cd976c5cfe65a45ef1bc4ac79bdfed/src/training/train.py), [src/models/watermark.py](https://github.com/Hubizon/SERUM/blob/02f4929e30cd976c5cfe65a45ef1bc4ac79bdfed/src/models/watermark.py), [SD2.1 config](https://github.com/Hubizon/SERUM/blob/02f4929e30cd976c5cfe65a45ef1bc4ac79bdfed/configs/config_sd21.yaml) | Normalized saved grid mixed with Gaussian noise. The pinned optimizer trains only the score model, despite the grid being an nn.Parameter. Loaded YAML controls model/sampling. Generation snapshots YAML and detector; detection uses VAE encoding plus CNN sigmoid, no inversion or user-message decoding. App requires 512x512 images / 4x64x64 latents. No calibrated threshold. |

## Defaults Are Not Live Configuration

The UI now labels the adapter's presets **Website defaults** and separately
shows **Upstream reference** with a reviewed source link. For the nine newer
methods, configurable presets are read directly from
`backend/config/repository_methods.json`, the same source used by the backend
and form controls. Server model overrides and saved job settings may differ.
Analysis uses linked state, not changed generation controls.

Important differences that must not be described as identical upstream defaults:

- Tree-Ring: upstream CLI `rand`, channel 0; website initial `ring`, channel 3.
- Ring-ID/WIND: upstream `assigned_keys=-1` means full bank; website uses 2048.
  Ring-ID chooses index 628 by default; WIND Full's M=10000 is not Fast's
  one-entry per-job registry size. The app does not implement an account registry.
- ROBIN: upstream CLI channel 0; website channel 3 and injection step 35.
  Matching optimized artifacts are essential, not an optional quality setting.
- TAG-WM: upstream `calc_wm_use_tamper_loc=False`; website enables it by default.
  SD2.1 path only. Message size defaults to 256, not a fixed capacity for all jobs.
- GaussMarker: upstream detector FPR 0.01; adapter watermark evaluator FPR 1e-6.
  The app reports the ensemble probability without applying either as a
  calibrated ensemble threshold.
- Gaussian Shading: upstream CLI without `--chacha` uses XOR; website selects
  ChaCha20 first. Default capacity 256 changes with the copy factors.
- Gaussian Shannon: function/notebook-oriented upstream. The wrapper's 256-bit
  Gaussian/LDPC profiles are website presets, not a universal upstream CLI.
- SFWMark: official single-prompt generation fixes seed 42. The seed control is
  now disabled for this method rather than suggesting arbitrary control.
- SERUM: model, guidance, sampling count and mixing alpha come from loaded YAML.
  The released SD2.1 example uses 50 steps, 7.5 guidance and alpha 0.5; these are
  reference values, not guaranteed settings for an arbitrary supplied config.

## Implementation Changes

- Explicit per-variant contracts replace first/last-graph-box-derived Needs and
  Returns. Graphs now change with the variant, and every workflow has its own row.
- Training and optimization are offline preparation, not website actions.
  Their disabled tabs and process rows have been removed; setup requirements
  remain in the method reference and setup guide.
- Linked-state language no longer calls every artifact a private key: SEAL
  stores configuration; SERUM stores its detector/configuration; LDPC needs H/G.
- LDPC verification is blocked in the UI until a generation job is linked,
  matching the runner requirement. Its result label now names BP with the
  vote-and-retry fallback instead of always saying majority vote.
- Removed incorrect LaWa pretrained-message/generative-decoder extraction
  wording and SERUM joint-optimization wording, including setup documentation.

## Validation Boundary

### Final UI Pass (2026-10-15)

Rechecked the original five source checkouts and the nine pinned upstream
revisions against the website adapters. The review preserves important limits:
Fourier distances are not probabilities; an index is not an account identity;
TAG-WM's mask is a prediction, not measured localization accuracy; SERUM's CNN
score has no calibrated website threshold. SERUM mixes normalized grid and
noise with square-root weights: `sqrt(1-alpha) * noise + sqrt(alpha) * grid_norm`.
Its released optimizer updates the detector, not the grid.

The main screen now contains runnable workflows, a separate row per process,
plain-text generated payload summaries and expandable source/default details.
Method categories crossfade without a timer-driven unmount. Inactive panes are
inert, keyboard focus is restored, and reduced-motion preferences are respected.
The analysis preview retains the complete image at its natural aspect ratio.

Fixed an analysis input bug: uploading an edited image no longer discards the
linked job's key/settings. Linking a job after uploading preserves the upload;
clearing the job selection clears its key. Failure results use an error icon,
and bit-accuracy results are no longer labeled as a generic verification score.

Validation completed: production build and lint pass; all 20 backend CPU tests
pass. The browser suite covers 14 methods / 21 variants and all exposed actions
using 52 mocked requests, plus source links, defaults, variant graphs, edited
image linkage in both selection orders, mask output, setup errors, keyboard
focus, reduced motion and 320-1440px responsive layouts.

Frontend build/lint, mocked browser contract tests and backend CPU contract tests
check UI wiring, defaults, variant-specific graphs, result labels, source-job
requirements and responsive layout. They do not measure watermark robustness,
false-positive rates, image quality or GPU memory. Real generation followed by
analysis of the original, edited and unrelated images remains necessary for
each configured server environment. Full attack sweeps, ROC calibration,
FID/CLIP evaluation, training and optimization remain offline research tasks.
