export type CategoryId = 'latent-noise' | 'vae-decoder' | 'dual-semantic' | 'optimization-tamper' | 'learned-detector'
export type RepositoryMethodId = 'tree-ring' | 'ring-id' | 'wind' | 't2smark' | 'gaussmarker' | 'seal' | 'robin' | 'tag-wm' | 'serum'
export type WorkflowId = 'generate' | 'verify' | 'detect' | 'decode' | 'identify' | 'localize'

export const categories: { id: CategoryId; name: string; detail: string; color: string }[] = [
  { id: 'latent-noise', name: 'Latent / Initial Noise', detail: 'Patterns and codes in diffusion noise', color: '#136f63' },
  { id: 'vae-decoder', name: 'VAE / Decoder', detail: 'Watermarks carried by the image decoder', color: '#315f9f' },
  { id: 'dual-semantic', name: 'Dual Domain / Semantic', detail: 'Combined signals and content-aware keys', color: '#9a3f58' },
  { id: 'optimization-tamper', name: 'Optimization / Tamper Aware', detail: 'Optimized watermarks and edit localization', color: '#8b6818' },
  { id: 'learned-detector', name: 'Learned Detector', detail: 'Detection with a trained latent classifier', color: '#526c42' },
]

type RepositoryMethod = {
  id: RepositoryMethodId
  name: string
  shortName: string
  categoryId: CategoryId
  category: string
  mechanism: string
  payload: string
}

export const repositoryMethods: RepositoryMethod[] = [
  {
    id: 'tree-ring', name: 'Tree-Ring', shortName: 'TR', categoryId: 'latent-noise', category: 'Fourier-pattern watermark',
    mechanism: 'Inserts a ring, random or zero pattern into the Fourier domain of initial noise and compares it after inversion.',
    payload: 'Keyed Fourier pattern',
  },
  {
    id: 'ring-id', name: 'Ring-ID', shortName: 'RID', categoryId: 'latent-noise', category: 'Multi-user Fourier watermark',
    mechanism: 'Combines heterogeneous and ring Fourier patterns, then compares inverted noise with the saved candidate bank.',
    payload: 'Pattern-bank identity',
  },
  {
    id: 'wind', name: 'WIND', shortName: 'WND', categoryId: 'latent-noise', category: 'Grouped noise identification',
    mechanism: 'Uses initial noise as a watermark, with a group identifier to narrow the search before matching the individual noise.',
    payload: 'Group identifier + noise identity',
  },
  {
    id: 't2smark', name: 'T2SMark', shortName: 'T2S', categoryId: 'latent-noise', category: 'Noise-as-watermark',
    mechanism: 'Encodes a session key under a master key in one noise channel and a message under that session key in the other channels. Decoding first recovers the session key.',
    payload: 'Session key + random message bits',
  },
  {
    id: 'gaussmarker', name: 'GaussMarker', shortName: 'GM', categoryId: 'dual-semantic', category: 'Dual-domain Gaussian watermark',
    mechanism: 'Combines spatial and frequency watermarks in initial Gaussian noise and uses a learned Gaussian Noise Restorer during detection.',
    payload: 'Bit watermark + frequency pattern',
  },
  {
    id: 'seal', name: 'SEAL', shortName: 'SL', categoryId: 'dual-semantic', category: 'Semantic-aware noise watermark',
    mechanism: 'Ties the noise watermark to image semantics and infers its key from semantic embeddings through locality-sensitive hashing.',
    payload: 'Semantic-derived watermark key',
  },
  {
    id: 'robin', name: 'ROBIN', shortName: 'RB', categoryId: 'optimization-tamper', category: 'Optimized intermediate-latent watermark',
    mechanism: 'Uses offline-optimized watermark and hiding conditioning at an intermediate diffusion state, then verifies the corresponding inverted state.',
    payload: 'Optimized watermark + hiding conditioning',
  },
  {
    id: 'tag-wm', name: 'TAG-WM', shortName: 'TAG', categoryId: 'optimization-tamper', category: 'Tamper-aware generative watermark',
    mechanism: 'Jointly embeds copyright and localization watermarks, uses inversion sensitivity to locate edits, and guides message recovery with the tamper map.',
    payload: 'Copyright message + localization signal',
  },
  {
    id: 'serum', name: 'SERUM', shortName: 'SRM', categoryId: 'learned-detector', category: 'Learned VAE-latent watermark detector',
    mechanism: 'Mixes a saved watermark grid with noise and uses an offline-trained latent CNN to score VAE-encoded images without diffusion inversion.',
    payload: 'Noise-grid presence signal',
  },
]
