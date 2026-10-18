# The Watermarking Library Frontend

The frontend groups 14 repository-backed watermark methods into five categories:

| Category | Methods |
| --- | --- |
| Latent / Initial Noise | SFWMark, Gaussian-Shannon, Gaussian Shading, PRC-Watermark, Tree-Ring, Ring-ID, WIND, T2SMark |
| VAE / Decoder | LaWa |
| Dual Domain / Semantic | GaussMarker, SEAL |
| Optimization / Tamper Aware | ROBIN, TAG-WM |
| Learned Detector | SERUM |

Each method exposes its implemented generation and native analysis actions.
Training, optimization and dataset evaluation run offline. Real inference requires
configured GPU runtimes and model/artifact files; a visible method is not proof
that its runtime is installed on the current machine.

Follow the [project installer](../README.md) for a complete setup. From the root:

```bash
bash setup.sh --ui-only
bash start.sh
```

For frontend development alone:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Use Node 22.12 or newer. The local frontend connects to port 8000 by default.
Set `VITE_API_BASE` and `VITE_FILE_BASE` for a different reachable backend, or
use `bash start.sh --frontend-only --api-url http://127.0.0.1:8000`.
A deployed frontend uses same-origin `/api` and `/files` routes unless overridden
at build time.

Generation history is per method and variant. Select the matching generated job
before analysis when saved watermark state is required. The frontend displays
watermarked images and native results, with full runner errors available for
debugging. It does not fabricate dataset-level ROC, FID or detection accuracy.
