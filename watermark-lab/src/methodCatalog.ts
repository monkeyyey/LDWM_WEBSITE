export type CategoryId = 'latent-noise' | 'vae-decoder' | 'dual-semantic' | 'optimization-tamper' | 'learned-detector'
export type RepositoryMethodId = 'tree-ring' | 'ring-id' | 'wind' | 't2smark' | 'gaussmarker' | 'seal' | 'robin' | 'tag-wm' | 'serum'
export type WorkflowId = 'generate' | 'verify' | 'detect' | 'decode' | 'identify' | 'optimize' | 'localize' | 'train'

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
  processes: { workflow: WorkflowId; label: string; steps: string[] }[]
}

export const repositoryMethods: RepositoryMethod[] = [
  {
    id: 'tree-ring', name: 'Tree-Ring', shortName: 'TR', categoryId: 'latent-noise', category: 'Fourier ring-pattern watermark',
    mechanism: 'Inserts a keyed ring pattern into the Fourier domain of initial diffusion noise and checks the recovered pattern after inversion.',
    payload: 'Keyed Fourier pattern',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + watermark key', 'Initial Gaussian noise', 'Fourier ring insertion', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'detect', label: 'Detection', steps: ['Image + expected pattern', 'Diffusion inversion', 'Fourier pattern comparison', 'Detection statistic'] },
    ],
  },
  {
    id: 'ring-id', name: 'Ring-ID', shortName: 'RID', categoryId: 'latent-noise', category: 'Multi-user Fourier watermark',
    mechanism: 'Assigns distinct Fourier watermark patterns to users and compares inverted noise with a candidate pattern bank.',
    payload: 'User-specific pattern identity',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + user pattern', 'Fourier watermark insertion', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'verify', label: 'Verification', steps: ['Image + linked key', 'Diffusion inversion', 'Expected-pattern distance'] },
      { workflow: 'identify', label: 'Identification', steps: ['Image + candidate pattern bank', 'Diffusion inversion', 'Candidate comparison', 'Predicted identity'] },
    ],
  },
  {
    id: 'wind', name: 'WIND', shortName: 'WND', categoryId: 'latent-noise', category: 'Grouped noise identification',
    mechanism: 'Uses initial noise as a watermark, with a group identifier to narrow the search before matching the individual noise.',
    payload: 'Group identifier + noise identity',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + grouped noise', 'Group watermark insertion', 'Diffusion generation', 'Image + saved noise'] },
      { workflow: 'identify', label: 'Identification', steps: ['Image + noise registry', 'Diffusion inversion', 'Group retrieval', 'Noise matching', 'Predicted identity'] },
    ],
  },
  {
    id: 't2smark', name: 'T2SMark', shortName: 'T2S', categoryId: 'latent-noise', category: 'Noise-as-watermark',
    mechanism: 'Encodes a session key under a master key in one noise channel and a message under that session key in the other channels. Decoding first recovers the session key.',
    payload: 'Session key + random message bits',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Master + session key', 'Key and message tail sampling', 'SD 2.1 generation', 'Watermarked image'] },
      { workflow: 'detect', label: 'Detection', steps: ['Image + master key', 'Diffusion inversion', 'Key-channel recovery', 'L1 detection statistic'] },
      { workflow: 'decode', label: 'Decoding', steps: ['Inverted noise + master key', 'Recover session key', 'Decode message with recovered key', 'Message bits + accuracy'] },
    ],
  },
  {
    id: 'gaussmarker', name: 'GaussMarker', shortName: 'GM', categoryId: 'dual-semantic', category: 'Dual-domain Gaussian watermark',
    mechanism: 'Combines spatial and frequency watermarks in initial Gaussian noise and uses a learned Gaussian Noise Restorer during detection.',
    payload: 'Bit watermark + frequency pattern',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + watermark keys', 'Spatial + frequency insertion', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'detect', label: 'Detection', steps: ['Image + keys + restorer checkpoint', 'Diffusion inversion', 'Gaussian Noise Restorer', 'Dual-domain analysis', 'Combined detection score'] },
      { workflow: 'train', label: 'Restorer training', steps: ['Watermark training data', 'Noise distortions', 'Train noise restorer', 'Restorer checkpoint'] },
    ],
  },
  {
    id: 'seal', name: 'SEAL', shortName: 'SL', categoryId: 'dual-semantic', category: 'Semantic-aware noise watermark',
    mechanism: 'Ties the noise watermark to image semantics and infers its key from semantic embeddings through locality-sensitive hashing.',
    payload: 'Semantic-derived watermark key',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Preliminary image generation', 'BLIP-2 caption + semantic embedding', 'Semantic noise derivation', 'Second diffusion generation', 'Watermarked image'] },
      { workflow: 'verify', label: 'Verification', steps: ['Image', 'Semantic embedding + inferred key', 'Diffusion inversion', 'Content-conditioned verification'] },
    ],
  },
  {
    id: 'robin', name: 'ROBIN', shortName: 'RB', categoryId: 'optimization-tamper', category: 'Optimized intermediate-latent watermark',
    mechanism: 'Optimizes a watermark and hiding prompt, inserts the watermark into an intermediate diffusion state, and verifies it by reversing generation.',
    payload: 'Optimized watermark + hiding prompt',
    processes: [
      { workflow: 'optimize', label: 'Optimization', steps: ['Clean reference images', 'Adversarial optimization', 'Optimized watermark + hiding prompt'] },
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + optimized artifacts', 'Intermediate-state insertion', 'Guided hiding process', 'Watermarked image'] },
      { workflow: 'verify', label: 'Verification', steps: ['Image + optimized watermark', 'Reverse generation', 'Watermark comparison', 'Verification result'] },
    ],
  },
  {
    id: 'tag-wm', name: 'TAG-WM', shortName: 'TAG', categoryId: 'optimization-tamper', category: 'Tamper-aware generative watermark',
    mechanism: 'Jointly embeds copyright and localization watermarks, uses inversion sensitivity to locate edits, and guides message recovery with the tamper map.',
    payload: 'Copyright message + localization signal',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + watermark configuration', 'Dual-mark joint sampling', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'localize', label: 'Tamper localization', steps: ['Possibly edited image', 'Diffusion inversion', 'Trained or train-free refinement', 'Tamper mask'] },
      { workflow: 'decode', label: 'Decoding', steps: ['Image + watermark state', 'Inversion + tamper map', 'Tamper-aware decoding', 'Recovered message'] },
    ],
  },
  {
    id: 'serum', name: 'SERUM', shortName: 'SRM', categoryId: 'learned-detector', category: 'Learned VAE-latent watermark detector',
    mechanism: 'Jointly trains a noise watermark and detector offline. Analysis VAE-encodes the image and scores its latents with the trained CNN, without diffusion inversion.',
    payload: 'Learned watermark presence signal',
    processes: [
      { workflow: 'train', label: 'Detector training', steps: ['Watermarked + clean training images', 'Offline detector training', 'Detector checkpoint'] },
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + fixed watermark noise', 'Noise mixing', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'detect', label: 'Detection', steps: ['Image + detector checkpoint', 'VAE encoding', 'Latent CNN forward pass', 'Watermark score'] },
    ],
  },
]
