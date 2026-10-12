# Watermark Lab

The frontend groups 14 watermark methods into five categories. Five methods
have repository integrations:

- SFWMark: HSQR and HSTR Fourier latent watermarking.
- Gaussian-Shannon: Gaussian and LDPC coded message watermarking.
- LaWa: the repository's pretrained 48-bit configuration.
- Gaussian Shading: simple XOR and ChaCha20 distribution-preserving Gaussian
  latent variants.
- PRC-Watermark: keyed pseudorandom-code generation, Detect, and Decode.

## Catalogue

| Category | Integrated | Planned |
| --- | --- | --- |
| Latent / Initial Noise | SFWMark, Gaussian Shannon, Gaussian Shading, PRC-Watermark | Tree-Ring, Ring-ID, WIND, T2SMark |
| VAE / Decoder | LaWa | - |
| Dual Domain / Semantic | - | GaussMarker, SEAL |
| Optimization / Tamper Aware | - | ROBIN, TAG-WM |
| Learned Detector | - | SERUM |

Select a category to view its methods. Planned methods have browsable process
rows and an explicit awaiting-implementation state. They have no executable
controls, job history, image preview, or results, and never call the backend.
Their workflows are preliminary outlines; exact parameters and artifact
requirements should be finalized against each repository during integration.

Category definitions and planned entries live in `src/methodCatalog.ts`.
Integrated method definitions and the existing request mapping live in
`src/App.tsx`. When adding an integration, replace its planned entry with an
integrated definition, implement its backend adapter, and supply its actual
workflows and submethods.

Integrated methods expose their own generation and analysis workflows.
Verification keeps the repository's own meaning: Fourier-pattern comparison for
SFWMark, message extraction and BER/accuracy for Gaussian-Shannon and LaWa.
Identification is disabled where the upstream repository has no candidate-key
identification procedure. Gaussian Shading's thresholded traceability metric
and PRC's separate Detect and Decode operations are represented directly. The
website does not add candidate-bank identification where the repositories do
not implement it.

## Run

```bash
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173/` while the backend is running on port 8000.

```bash
python3 ../backend/server.py --port 8000
```

The frontend never displays or downloads a clean comparison image. Generated
outputs are the watermarked images returned by the selected repository runner.
