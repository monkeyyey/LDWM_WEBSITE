# Watermark Lab

The frontend is a single environment for exploring five upstream latent-domain
watermark repositories:

- SFWMark: HSQR and HSTR Fourier latent watermarking.
- Gaussian-Shannon: Gaussian and LDPC coded message watermarking.
- LaWa: the repository's pretrained 48-bit configuration.
- Gaussian Shading: simple XOR and ChaCha20 distribution-preserving Gaussian
  latent variants.
- PRC-Watermark: keyed pseudorandom-code generation, Detect, and Decode.

Each method is organized around Generation, Verification, and Identification.
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
