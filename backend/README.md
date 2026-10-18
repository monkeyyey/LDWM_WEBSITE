# Watermark Backend

The Python gateway translates website requests into the native generation and
analysis workflows of 14 watermark methods. Each method runs in a separate
process using its configured Python environment and upstream source.

Start with the [project setup guide](../README.md):

```bash
bash setup.sh --artifacts /path/to/ldwm-artifacts --download-models
bash start.sh
```

The gateway uses Python's standard library; GPU dependencies belong in the
method runtimes, not in one shared gateway environment. The older
`requirements.gpu.txt` is retained for existing installations and is not a
requirements file for all 14 methods.

## Methods

- SFWMark: HSQR/HSTR generation, known-pattern verification and identification.
- Gaussian-Shannon: Gaussian/LDPC generation and message extraction.
- LaWa: generation and extraction using the supplied 48-bit decoder.
- Gaussian Shading: simple/ChaCha generation and bit-accuracy threshold analysis.
- PRC-Watermark: generation, Detect and Decode.
- Tree-Ring: ring/random/zero generation and Fourier-distance analysis.
- Ring-ID: generation, known-key verification and candidate-bank identification.
- WIND: full/fast generation and registered-noise identification.
- T2SMark: generation, key detection and message decoding.
- GaussMarker: generation and dual-domain analysis with the matched W1/GNR.
- SEAL: semantic-noise generation and image-conditioned patch-distance analysis.
- ROBIN: generation and intermediate-inversion verification using optimized state.
- TAG-WM: trainable/trainfree generation, decoding and tamper localization.
- SERUM: generation and trained latent-detector scoring.

Training, optimization and benchmark sweeps are offline upstream workflows.
See [method setup and limitations](../docs/REPOSITORY_METHOD_SETUP.md).

## API

```text
GET  /health
GET  /methods
GET  /jobs?method=tree-ring&submethod=ring
POST /watermark/generate
POST /detect
GET  /files/<path>
```

POST requests accept `method`, `submethodId`, `analysisMode`, `prompt`,
`message`, `seed`, `imageDataUrl`, `sourceJobId` and `options`. Analysis
must select a compatible generated job wherever the method needs saved keys or
state. An edited image can be analyzed against that job. There is no generic
uploaded-image watermark insertion operation.

The gateway automatically loads the root `.env.gpu` without executing it as
shell code. Exported environment values take precedence. Use absolute paths in
that file. The installer writes machine-specific paths and creates a backup
before replacing existing configuration.

Generated images, metadata and private state live under `backend/storage/`.
Private checkpoint/key files cannot be downloaded through `/files/`. Keep
backups of generation state; an image alone is insufficient for most linked
analysis workflows.

The API has no built-in authentication or GPU queue. Keep it local or behind
authenticated access, and run one GPU job at a time.

## Validation

```bash
bash setup.sh --check
python3 -m unittest discover -s backend/tests -v
```

Import checks do not prove GPU inference or watermark quality. Validate generation,
each analysis action, edited images and analysis after a backend restart on the
target GPU. Missing setup returns an error instead of a simulated successful job.
