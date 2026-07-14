# Watermark Lab

Minimal local-first prototype for testing latent-domain image watermarking workflows.

## Workflows

- Upload an image and apply a selected watermarking method.
- Generate a new watermarked image from a prompt.

The current version uses mock results in the browser. The UI is ready for model services, but it does not run SFWMark, Gaussian Shannon, or LaWa yet.

## Run Locally

```bash
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:5173/
```

## Build

```bash
pnpm build
```

## Future Model API Shape

Recommended backend endpoints:

```text
POST /api/watermark/upload
POST /api/watermark/generate
POST /api/detect
POST /api/attack
```

Each model should be wrapped behind the same request/response contract so the frontend can switch between SFWMark, Gaussian Shannon, and LaWa without model-specific UI code.
