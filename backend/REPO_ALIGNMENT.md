# Repository Alignment

The application is an aggregation layer, not a replacement implementation.
Each adapter calls the corresponding upstream repository or a thin runner that
imports its functions and preserves its data flow.

## SFWMark

Repository: `work/repos/SFWMark`

- Generation starts from Gaussian latent noise shaped `1 x 4 x 64 x 64`, inserts
  the selected Fourier pattern, and runs Stable Diffusion.
- Verification uses DDIM inversion and distance to the known ground-truth
  pattern. The original repository uses this distance in ROC evaluation.
- Identification computes distances to the 2048-pattern bank, chooses the
  closest candidate, and only then compares it with the stored ground-truth
  index for accuracy.
- The website exposes the fully wired `HSQR` and `HSTR` variants. Tree-Ring and
  RingID are not part of this app's SFWMark selection.

The browser shows only the watermarked output. The generation job retains the
pattern bank and ground-truth index required for later analysis.

## Gaussian-Shannon

Repository: `work/repos/Gaussian-Shannon`

- Generation uses the repository's Gaussian or LDPC coding functions, embeds
  the coded bits into the diffusion latent, and generates an image.
- Verification is represented by inversion, extraction, and comparison with
  the supplied 256-bit message.
- The repository reports bit error rate rather than a candidate-key identity.
The adapter runner calls the repository's `gauss_encode`, `ldpc_encode`,
`watermarkToLatents`, `latentsToWatermark`, and decoder functions.

## LaWa

Repository: `work/repos/LaWa`

- Generation calls the original `inference_AIGC.py` with the pretrained 48-bit
  message configuration.
- Verification uses the modified decoder to extract 48 bits and reports bit
  accuracy and bit error rate.
- The repository has no candidate-bank identification procedure.

The extraction runner loads the same LaWa model and calls its `model.decoder`
path. It does not claim arbitrary-image watermark embedding.

## Gaussian Shading

Repository: `work/repos/Gaussian-Shading`

- Generation uses the upstream `Gaussian_Shading` or
  `Gaussian_Shading_chacha` class. The class generates the watermark and key,
  diffuses the bits with the configured copy factors, and creates the initial
  latent through truncated-Gaussian sampling.
- Verification follows the upstream empty-prompt DDIM inversion and
  `eval_watermark` logic. The app reports recovered bit accuracy, BER, and the
  separate detection and multi-user traceability threshold decisions.
- The simple and ChaCha20 variants are separate submethods because the upstream
  README states that the simple randomization is not strictly
  performance-lossless.
- Traceability is a thresholded known-watermark test. The repository does not
  search a candidate key bank, so identification is unavailable.

## PRC-Watermark

Repository: `work/repos/PRC-Watermark`

- Generation follows `encode.py`: `KeyGen`, `Encode` without a supplied user
  message, pseudogaussian sampling, and Stable Diffusion generation.
- Detect and Decode are separate analysis operations: both use exact inversion
  with an empty prompt and posterior recovery with variance 1.5 by default;
  Detect calls `Detect` and Decode calls `Decode` independently. The original
  `decode.py` invokes both and calculates an optional `Detect OR Decode-valid`
  decision, but the website does not collapse them into a generic verification
  action.
- The released product result is binary. The website does not present PRC as a
  long-message extractor or candidate-bank identifier.
- Both operations require the decoding key stored with a compatible generation
  job.

## Product Boundary

These repositories watermark during generation. The shared app therefore
supports:

```text
prompt -> repository-native watermark generation -> watermarked image
       -> repository-native verification or identification
```

It does not offer a generic post-hoc operation that takes an arbitrary image and
adds a watermark. No clean comparison image is returned or downloadable.

## Runtime Truthfulness

There are no generic mock adapters or built-in fallback algorithms. If a
repository checkout, dependency, checkpoint, or accelerator is missing, the
backend returns `setup_required` or `failed` and includes the runner logs.
