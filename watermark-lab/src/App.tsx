import {
  Activity,
  Aperture,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Copy,
  Download,
  ExternalLink,
  Gauge,
  ImageUp,
  KeyRound,
  Layers,
  LoaderCircle,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Waves,
} from 'lucide-react'
import { type ChangeEvent, type CSSProperties, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { categories, repositoryMethods, type CategoryId, type RepositoryMethodId, type WorkflowId } from './methodCatalog'
import repositoryCatalog from '../../backend/config/repository_methods.json'
import { repositorySubmethods, type WorkflowSpec, type SubmethodSpec, type ProcessSpec } from './repositoryDetails'

type OptionSpec = { label: string; type: string; default: number; min?: number; max?: number; step?: number; choices?: number[] }
type RepositorySpec = { variants: string[]; adapter_workflows: string[]; options: Record<string, OptionSpec>; repo_url: string }
const repositorySpecs: Partial<Record<MethodId, RepositorySpec>> = repositoryCatalog

type MethodId = 'sfwmark' | 'gaussian-shannon' | 'lawa' | 'gaussian-shading' | 'prc-watermark' | RepositoryMethodId
type BackendWorkflow = 'detect' | 'generate'

type Method = {
  id: MethodId
  name: string
  shortName: string
  categoryId: CategoryId
  category: string
  mechanism: string
  bestFor: string
  color: string
  processes: ProcessSpec[]
  submethods: SubmethodSpec[]
}

type Result = {
  status: 'idle' | 'running' | 'done'
  workflow: WorkflowId
  title: string
  score: number
  bits: string
  bitErrorRate?: string
  runtime: string
  notes: string
  raw?: BackendResult['raw']
  imageUrl?: string | null
  isError?: boolean
  errorDetails?: string
  jobId?: string | null
  jobNumber?: number | null
}

type BackendResult = {
  job_id?: string
  status: string
  workflow: BackendWorkflow
  detection_score: number
  recovered_payload: string
  runtime: string
  image_url?: string | null
  raw?: {
    summary?: string
    metrics?: { label: string; value: number | string | boolean }[]
    mask_url?: string
    wm_type?: string
    model_id?: string
    matched?: boolean
    key_index?: number
    predicted_index?: number
    distance?: number
    bit_error_rate?: number
    bit_accuracy?: number
    coding?: string
    redundancy?: number
    num_elements?: number
    latent_shape?: number[]
    decoder?: string
    analysis_mode?: string
    identified?: boolean
    verification_distance?: number
    source_job_id?: string
    job_number?: number
    gaussian_shading_variant?: string
    detected?: boolean
    traceable?: boolean
    tau_detection?: number
    tau_traceability?: number
    fpr?: number
    user_number?: number
    channel_copy?: number
    hw_copy?: number
    mark_length?: number
    detection_result?: boolean
    decoding_result?: boolean
    combined_result?: boolean
    decision_rule?: string
    operation?: string
    posterior_length?: number
    noise_rate?: number
    test_bit_count?: number
    max_bp_iter?: number
    message_available?: boolean
    prc_t?: number
    posterior_variance?: number
    codeword_length?: number
    inversion_order?: number
    inversion_prompt?: string
    error?: string
  }
  logs?: string[]
}

type RepositoryOptions = {
  [key: string]: number
  fpr: number
  user_number: number
  channel_copy: number
  hw_copy: number
  prc_t: number
  posterior_variance: number
  inference_steps: number
}

type JobSummary = {
  job_id: string
  job_number?: number
  label: string
  prompt: string
  method: MethodId
  submethod_id: string
  wm_type: string
  message?: string
  created_at?: string
  image_url: string
}

const sfwmarkWorkflow: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Sample Gaussian latent noise, insert the Fourier watermark, and generate the watermarked image.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', 'HSQR or HSTR', 'Configured diffusion model'], outputs: ['Watermarked image', 'Saved 2048-pattern bank and ground-truth index'], source: 'The official CLI fixes the single-image seed to 42; the website seed is not forwarded. Clean companion images remain internal.' },
  { id: 'verify', label: 'Verification', description: 'Compare the inverted latent with the expected saved watermark pattern.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Compatible generation job'], outputs: ['Fourier L1 verification distance'], source: 'Uses the saved pattern and key artifacts. The shared runner also computes candidate distances; verification displays the known-pattern distance, not a thresholded presence decision.' },
  { id: 'identify', label: 'Identification', description: 'Search the candidate pattern bank and return the closest predicted watermark index.', backendWorkflow: 'detect', available: true, inputs: ['Watermarked image', 'Compatible generation job'], outputs: ['Predicted pattern index', 'Correct/incorrect against stored key'], source: 'Searches the saved 2048-pattern bank' },
]

const gaussianWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Encode a 256-bit message into a redundant latent representation before diffusion generation.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', '256-bit binary message', 'Seed'], outputs: ['Watermarked image', 'Coding metadata'], source: 'No source job required' },
  { id: 'verify', label: 'Verification', description: 'Extract the 256-bit message and compare with the expected message.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Expected 256-bit message', 'Matching model and coding settings'], outputs: ['Recovered 256 bits', 'Bit accuracy and BER'], source: 'Gaussian coding uses sign recovery and majority voting after DDIM inversion. A linked job is optional for this variant; the runner uses inversion prompt "man", guidance 1 and 50 steps.' },
  { id: 'identify', label: 'Identification', description: 'The upstream Gaussian-Shannon repo has no candidate-key identification workflow.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'No candidate-key identification procedure is implemented.' },
]

const lawaWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Generate with a pretrained LaWa-modified VAE decoder and the supplied 48-bit message.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', '48-bit binary message', 'Seed', 'SD v1.4 and LaWa checkpoints'], outputs: ['Watermarked image'], source: 'Calls inference_AIGC.py. Only the watermarked image is exposed; clean/difference images and benchmark evaluations are not website results.' },
  { id: 'verify', label: 'Verification', description: 'Extract the 48-bit message with the pretrained message extractor and compare with expected bits.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Expected 48-bit message', 'Matching LaWa extractor checkpoint'], outputs: ['Recovered 48 bits', 'Bit accuracy', 'Bit error rate'], source: 'Calls model.decoder, the separate MessageDecoder network, not the generative VAE decoder. No diffusion inversion or linked generation job is required.' },
  { id: 'identify', label: 'Identification', description: 'The upstream LaWa repo has no candidate-key identification workflow.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'LaWa decodes a message but does not search a candidate-key bank.' },
]

const gaussianShadingWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Generate a random watermark, diffuse and randomize it, then use distribution-preserving truncated-Gaussian sampling for the initial latent.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', 'Simple XOR or ChaCha20', 'Copy factors', 'FPR and user count', 'Seed'], outputs: ['Watermarked image', 'Saved key', 'Generated watermark bits'], source: 'The upstream class generates the watermark and key; no user message is supplied' },
  { id: 'verify', label: 'Verification', description: 'Invert the image with an empty prompt, decrypt with the linked job key, vote over redundant copies, and compare the recovered watermark.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Compatible generation job and saved key'], outputs: ['Recovered bits', 'Bit accuracy and BER', 'Detection decision', 'Traceability decision'], source: 'Uses the upstream bit-accuracy evaluation and its FPR-derived thresholds' },
  { id: 'identify', label: 'Identification', description: 'The upstream repository does not search a candidate watermark bank.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'Traceability is a thresholded known-watermark test, not candidate-bank identification.' },
]

const prcWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Generate PRC encoding and decoding keys, encode a random keyed codeword, map it to pseudogaussian noise, and generate the image.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', 'Target FPR', 'Parity-check sparsity t', 'Seed'], outputs: ['Watermarked image', 'Saved encoding and decoding keys'], source: 'The released encode.py calls Encode without a user message' },
  { id: 'detect', label: 'Detect', description: 'Run exact inversion, recover a posterior vector, and apply the repository statistical Detect function with the key FPR.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Compatible generation job with decoding key'], outputs: ['Statistical Detect boolean'], source: 'Computes posteriors internally and calls src.prc.Detect. FPR comes from the saved key; neither a posterior vector nor a separate FPR is supplied during analysis.' },
  { id: 'decode', label: 'Decode', description: 'Run exact inversion, recover a posterior vector, and run belief propagation plus test-bit validation from the decoding key.', backendWorkflow: 'detect', available: true, inputs: ['Image', 'Compatible generation job with decoding key'], outputs: ['Decode-valid boolean'], source: 'Computes posteriors internally and calls src.prc.Decode using the BP limit stored in the key. The website generator supplies no user message, so the result reports validity only.' },
  { id: 'identify', label: 'Identification', description: 'The released repository does not search across account or key candidates.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'PRC-Watermark provides keyed binary detection, not candidate-bank identification.' },
]

const gaussianZeroMessage = '0'.repeat(256)

function sfwProcesses(variant: 'HSQR' | 'HSTR'): ProcessSpec[] {
  return [
    { workflow: 'generate', label: 'Generation', steps: ['Build 2048-pattern bank', variant === 'HSQR' ? 'QR sign pattern, channel 3' : 'Hermitian rings + heterogeneous channel', 'Fourier insertion in 44 x 44 center', 'Stable Diffusion generation', 'Image + bank + expected index'] },
    { workflow: 'verify', label: 'Verification', steps: ['Image + expected pattern', 'Empty-prompt DDIM inversion', variant === 'HSQR' ? 'QR-reference complex L1 distance' : 'Masked complex L1 distance', 'Known-pattern distance (no threshold)'] },
    { workflow: 'identify', label: 'Identification', steps: ['Image + saved 2048-pattern bank', 'Empty-prompt DDIM inversion', variant === 'HSQR' ? 'QR candidate distance search' : 'Ring candidate distance search', 'Closest index + label correctness'] },
  ]
}

function gaussianProcesses(ldpc: boolean): ProcessSpec[] {
  return [
    { workflow: 'generate', label: 'Generation', steps: ['Prompt + 256-bit message', ldpc ? 'LDPC encoding + 16 redundant copies' : '64 redundant copies', 'Pseudo-random flips + Gaussian mapping', 'DDIM generation', ldpc ? 'Image + saved H/G matrices' : 'Watermarked image'] },
    { workflow: 'verify', label: 'Verification', steps: ['Image + expected message', 'VAE mean + DDIM inversion', 'Extract symbols + undo sign flips', ldpc ? 'LDPC BP; vote-and-retry fallback' : 'Majority vote across copies', 'Recovered 256 bits + BER'] },
  ]
}

function shadingProcesses(chacha: boolean): ProcessSpec[] {
  return [
    { workflow: 'generate', label: 'Generation', steps: ['Random watermark bits', 'Repeat across channels and space', chacha ? 'ChaCha20 encryption' : 'XOR with random binary key', 'Truncated-Gaussian sampling', 'Diffusion generation + saved key'] },
    { workflow: 'verify', label: 'Verification', steps: ['Image + linked key', 'Empty-prompt DDIM inversion', chacha ? 'ChaCha20 decryption' : 'XOR key recovery', 'Vote across redundant copies', 'Bit accuracy + BER', 'Detection + traceability thresholds'] },
  ]
}

const ldpcWorkflows = gaussianWorkflows.map((flow): WorkflowSpec => flow.id === 'verify' ? {
  ...flow, inputs: ['Image', 'Expected 256-bit message', 'Compatible generation job with H/G matrices'],
  source: 'Tries LDPC belief propagation on each redundant copy; if all parity checks fail, votes across copies and retries BP. Saved H/G matrices are required. The runner uses inversion prompt "man", guidance 1 and 50 steps.',
} : flow.id === 'generate' ? { ...flow, outputs: ['Watermarked image', 'Saved H/G coding matrices and metadata'] } : flow)

const methods: Method[] = [
  {
    id: 'sfwmark',
    name: 'SFWMark',
    shortName: 'SFW',
    categoryId: 'latent-noise',
    category: 'Fourier latent watermark',
    mechanism: 'Embeds a keyed pattern into the Fourier space of Gaussian latent noise before Stable Diffusion generation.',
    bestFor: 'Pattern verification and identification from a generated image after DDIM inversion.',
    color: '#136f63',
    processes: [],
    submethods: [
      { id: 'hsqr', name: 'HSQR', description: 'Hermitian-symmetric QR sign pattern embedded through real/imaginary Fourier coefficients in the latent center.', payload: 'Pattern-bank index; no arbitrary text payload', defaultMessage: 'HSQR', messageMode: 'variant', repoDefaults: ['wm_type: HSQR', 'Channel: 3', 'Center: 44 x 44', 'Patterns: 2048', 'Seed: fixed 42', 'Steps: 50', 'Guidance: 7.5'], upstreamDefaults: 'src/utils.py defines QR version 1, box size 2, delta 0, channel 3 and watermark seed 7433. The official single-prompt CLI fixes seed 42 and produces a clean companion internally.', sourceUrl: 'https://github.com/thomas11809/SFWMark/blob/78666128b44614a0cc471993649e3132d5dddfcb/src/generate.py', workflows: sfwmarkWorkflow, processes: sfwProcesses('HSQR') },
      { id: 'hstr', name: 'HSTR', description: 'Hermitian-symmetric tree rings plus a heterogeneous pattern, with center-aware Fourier insertion.', payload: 'Pattern-bank index; no arbitrary text payload', defaultMessage: 'HSTR', messageMode: 'variant', repoDefaults: ['wm_type: HSTR', 'Channels: 0 + 3', 'Center: 44 x 44', 'Patterns: 2048', 'Seed: fixed 42', 'Steps: 50', 'Guidance: 7.5'], upstreamDefaults: 'src/generate.py calls make_Fourier_treering_pattern with hs=True, center=True and heter=True. The 2048-pattern bank uses watermark seeds starting at 7433.', sourceUrl: 'https://github.com/thomas11809/SFWMark/blob/78666128b44614a0cc471993649e3132d5dddfcb/src/generate.py', workflows: sfwmarkWorkflow, processes: sfwProcesses('HSTR') },
    ],
  },
  {
    id: 'gaussian-shannon',
    name: 'Gaussian Shannon',
    shortName: 'GS',
    categoryId: 'latent-noise',
    category: 'Communication-code watermark',
    mechanism: 'Treats generation and inversion as a noisy channel, using redundancy and coding to recover exact bits.',
    bestFor: 'Message verification and bit error measurement after inversion.',
    color: '#7a4f00',
    processes: [],
    submethods: [
      { id: 'gaussian', name: 'Gaussian coding', description: 'Repeated message bits with pseudo-random sign flips and majority-vote recovery after inversion.', payload: 'User-supplied 256-bit message', defaultMessage: gaussianZeroMessage, repoDefaults: ['Message: 256 bits', 'Redundancy: 64', 'Scheduler: DDIM', 'Steps: 50', 'Guidance: 7.5'], upstreamDefaults: 'The repository exposes coding functions and experiment notebooks, not a single global CLI preset. This adapter selects 256 bits, 64 copies and DDIM sampling.', sourceUrl: 'https://github.com/Rambo-Yi/Gaussian-Shannon/blob/ad89a75bc92001777637c6cc242a31188934e082/ldpc.py', workflows: gaussianWorkflows, processes: gaussianProcesses(false) },
      { id: 'ldpc', name: 'LDPC coding', description: 'LDPC error-correcting coding with redundant copies, pseudo-random sign flips and belief-propagation decoding; voting is followed by another BP attempt when all copies fail.', payload: 'User-supplied 256-bit message', defaultMessage: gaussianZeroMessage, repoDefaults: ['Message: 256 bits', 'Code rate: 0.25', 'Redundancy: 16', 'BP iterations: 100', 'SNR: 0', 'Steps: 50'], upstreamDefaults: 'ldpc_decode tries each copy with BP and parity checks. table_decision=True enables vote-and-retry on failure. The adapter saves the generated H/G matrices; it does not regenerate them during verification.', sourceUrl: 'https://github.com/Rambo-Yi/Gaussian-Shannon/blob/ad89a75bc92001777637c6cc242a31188934e082/ldpc.py', workflows: ldpcWorkflows, processes: gaussianProcesses(true) },
    ],
  },
  {
    id: 'lawa',
    name: 'LaWa',
    shortName: 'LW',
    categoryId: 'vae-decoder',
    category: 'VAE decoder watermark',
    mechanism: 'Uses a pretrained modified VAE decoder to embed supplied bits during generation, and a separate message extractor for verification.',
    bestFor: '48-bit message extraction without diffusion inversion.',
    color: '#315f9f',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + 48-bit message', 'Stable Diffusion sampling', 'LaWa modified VAE decoder', 'Watermarked image'] },
      { workflow: 'verify', label: 'Verification', steps: ['Watermarked image', 'Pretrained message decoder', 'Recovered 48 bits + BER'] },
    ],
    submethods: [
      { id: 'lawa-48', name: 'LaWa 48-bit', description: 'This website uses the released SD v1.4 configuration with a configurable 48-bit message.', payload: 'User-supplied 48-bit message', defaultMessage: '110111001110110001000000011101000110011100110101', repoDefaults: ['Config: SD14_LaWa_inference.yaml', 'Message: 48 bits', 'Steps: 50', 'Image: 512 x 512', 'SD checkpoint: weights/stable-diffusion-v1/model.ckpt'], upstreamDefaults: 'The released inference configuration pairs the KL-f8 modified decoder with a separate MessageDecoder and weights/LaWa/last.ckpt. Model paths may be overridden on the server.', sourceUrl: 'https://github.com/vbdi/LaWa/blob/251ac11aa223e6ff12553364a65a75add5b1aecf/configs/SD14_LaWa_inference.yaml', workflows: lawaWorkflows },
    ],
  },
  {
    id: 'gaussian-shading',
    name: 'Gaussian Shading',
    shortName: 'GSh',
    categoryId: 'latent-noise',
    category: 'Distribution-preserving latent watermark',
    mechanism: 'Diffuses a repository-generated bit watermark, randomizes it with XOR or ChaCha20, and samples each latent value from the matching half of a Gaussian distribution.',
    bestFor: 'Training-free keyed watermark verification with FPR-derived detection and traceability thresholds.',
    color: '#9a3f58',
    processes: [],
    submethods: [
      { id: 'chacha', name: 'ChaCha20', description: 'The distribution-preserving construction encrypts repeated watermark bits with a random ChaCha20 key and nonce.', payload: 'Generated bits; capacity depends on copy factors', defaultMessage: 'Generated by Gaussian Shading', messageMode: 'generated', repoDefaults: ['channel_copy: 1', 'hw_copy: 8', 'Capacity: 256 bits', 'FPR: 1e-6', 'Users: 1,000,000', 'Steps: 50', 'Guidance: 7.5'], upstreamDefaults: 'run_gaussian_shading.py uses channel_copy=1, hw_copy=8, FPR=1e-6 and 1,000,000 users. ChaCha20 is enabled with --chacha; the website selects it by default. Capacity is 16384 / (channel_copy * hw_copy^2).', sourceUrl: 'https://github.com/bsmhmmlf/Gaussian-Shading/blob/09c678fadc7545acf7be12647ddf2a5e66f6a9dc/run_gaussian_shading.py', workflows: gaussianShadingWorkflows, processes: shadingProcesses(true) },
      { id: 'simple', name: 'Simple XOR', description: 'Randomizes repeated bits with a random binary XOR key; the upstream README does not claim strict performance-losslessness for this variant.', payload: 'Generated bits; capacity depends on copy factors', defaultMessage: 'Generated by Gaussian Shading', messageMode: 'generated', repoDefaults: ['channel_copy: 1', 'hw_copy: 8', 'Capacity: 256 bits', 'FPR: 1e-6', 'Users: 1,000,000', 'Steps: 50', 'Guidance: 7.5'], upstreamDefaults: 'The upstream CLI uses Simple XOR when --chacha is absent. Copy factors and FPR settings match the ChaCha path, but the README qualifies the distribution guarantee for this faster baseline.', sourceUrl: 'https://github.com/bsmhmmlf/Gaussian-Shading/blob/09c678fadc7545acf7be12647ddf2a5e66f6a9dc/README.md', workflows: gaussianShadingWorkflows, processes: shadingProcesses(false) },
    ],
  },
  {
    id: 'prc-watermark',
    name: 'PRC-Watermark',
    shortName: 'PRC',
    categoryId: 'latent-noise',
    category: 'Pseudorandom-code latent watermark',
    mechanism: 'Encodes a keyed pseudorandom codeword, maps its signs to pseudogaussian initial noise, and applies Detect or Decode after exact diffusion inversion.',
    bestFor: 'Keyed statistical detection and decode-validity testing at a target false-positive rate.',
    color: '#34766f',
    processes: [
      { workflow: 'generate', label: 'Generation', steps: ['Prompt + PRC key generation', 'Random keyed codeword', 'Pseudogaussian latent, 1 x 4 x 64 x 64', 'Diffusion generation', 'Watermarked image'] },
      { workflow: 'detect', label: 'Detect', steps: ['Watermarked image + decoding key', 'Exact inversion', 'Posterior vector', 'Statistical Detect decision'] },
      { workflow: 'decode', label: 'Decode', steps: ['Watermarked image + decoding key', 'Exact inversion', 'Posterior vector', 'Belief propagation + validity'] },
    ],
    submethods: [
      { id: 'prc', name: 'PRC', description: 'The released implementation uses a 16,384-symbol PRC codeword. Detect and Decode are separate operations; the upstream decode.py also reports their OR combination.', payload: 'Random keyed PRC codeword; no user message', defaultMessage: 'Generated keyed PRC codeword', messageMode: 'generated', repoDefaults: ['Codeword: 16,384 symbols', 'FPR: 1e-5', 'Parity sparsity t: 3', 'Posterior variance: 1.5', 'Inversion order: 0', 'Steps: 50'], upstreamDefaults: 'encode.py uses KeyGen then Encode without a user message. decode.py calls both Detect and Decode; the website exposes them independently and does not return their OR as the selected action.', sourceUrl: 'https://github.com/XuandongZhao/PRC-Watermark/blob/3f372c1d9cafcd0732331c0d00f0430ee822a389/decode.py', workflows: prcWorkflows },
    ],
  },
  ...repositoryMethods.map((method): Method => ({
    ...method,
    bestFor: method.payload,
    color: categories.find((category) => category.id === method.categoryId)!.color,
    processes: [],
    submethods: repositorySubmethods(method.id, method.name),
  })),
]

function defaultRepositoryOptions(methodId: MethodId): RepositoryOptions {
  return {
    fpr: methodId === 'prc-watermark' ? 0.00001 : 0.000001,
    user_number: 1000000,
    channel_copy: 1,
    hw_copy: 8,
    prc_t: 3,
    posterior_variance: 1.5,
    inference_steps: 50,
    ...Object.fromEntries(Object.entries(repositorySpecs[methodId]?.options ?? {}).map(([key, spec]) => [key, spec.default])),
  }
}

const currentLocation = globalThis.location
const isLocalFrontend = currentLocation?.hostname === 'localhost' || currentLocation?.hostname === '127.0.0.1' || currentLocation?.hostname === ''
const apiBase = import.meta.env.VITE_API_BASE ?? (isLocalFrontend ? `${currentLocation?.protocol ?? 'http:'}//${currentLocation?.hostname ?? '127.0.0.1'}:8000` : `${currentLocation?.origin ?? ''}/api`)
const fileBase = import.meta.env.VITE_FILE_BASE ?? (isLocalFrontend ? apiBase : (currentLocation?.origin ?? ''))

function App() {
  const [categoryId, setCategoryId] = useState<CategoryId>('latent-noise')
  const [selectorView, setSelectorView] = useState<'categories' | 'methods'>('categories')
  const [customUpload, setCustomUpload] = useState(false)
  const [workflowId, setWorkflowId] = useState<WorkflowId>('generate')
  const [methodId, setMethodId] = useState<MethodId>('sfwmark')
  const [submethodId, setSubmethodId] = useState(methods[0].submethods[0].id)
  const [prompt, setPrompt] = useState('a clean product photo of a ceramic mug on a desk')
  const [message, setMessage] = useState(methods[0].submethods[0].defaultMessage)
  const [seed, setSeed] = useState(42)
  const [repositoryOptions, setRepositoryOptions] = useState<RepositoryOptions>(defaultRepositoryOptions('sfwmark'))
  const [uploadName, setUploadName] = useState('No image selected')
  const [uploadedImage, setUploadedImage] = useState<string | null>(null)
  const [sourceJobId, setSourceJobId] = useState<string | null>(null)
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [selectedJobId, setSelectedJobId] = useState('')
  const [copiedErrorDetails, setCopiedErrorDetails] = useState(false)
  const [result, setResult] = useState<Result>({ status: 'idle', workflow: 'generate', title: 'Ready', score: 0, bits: '--', runtime: '--', notes: 'Choose a method, submethod, and workflow, then run the repository-backed action.', imageUrl: null })
  const runTokenRef = useRef(0)
  const requestInFlightRef = useRef(false)
  const uploadReaderRef = useRef<FileReader | null>(null)
  const categoryBackRef = useRef<HTMLButtonElement | null>(null)
  const categoryButtonRefs = useRef<Partial<Record<CategoryId, HTMLButtonElement | null>>>({})

  const selectedMethod = useMemo(() => methods.find((method) => method.id === methodId) ?? methods[0], [methodId])
  const selectedCategory = categories.find((category) => category.id === categoryId) ?? categories[0]
  const categoryMethods = methods.filter((method) => method.categoryId === categoryId)
  const repositorySpec = repositorySpecs[selectedMethod.id]
  const selectedSubmethod = useMemo(() => selectedMethod.submethods.find((submethod) => submethod.id === submethodId) ?? selectedMethod.submethods[0], [selectedMethod, submethodId])
  const selectedWorkflow = useMemo(() => selectedSubmethod.workflows.find((workflow) => workflow.id === workflowId) ?? selectedSubmethod.workflows[0], [selectedSubmethod, workflowId])
  const isGeneration = selectedWorkflow.id === 'generate'
  const needsImage = !isGeneration
  const isSfwAnalysis = selectedMethod.id === 'sfwmark' && !isGeneration
  const isPrcAnalysis = selectedMethod.id === 'prc-watermark' && (selectedWorkflow.id === 'detect' || selectedWorkflow.id === 'decode')
  const isPrcDetect = selectedWorkflow.id === 'detect'
  const usesGeneratedPayload = selectedSubmethod.messageMode === 'generated'
  const requiresSourceKey = Boolean(repositorySpec) || ['sfwmark', 'gaussian-shading', 'prc-watermark'].includes(selectedMethod.id) || (selectedMethod.id === 'gaussian-shannon' && selectedSubmethod.id === 'ldpc')
  const messageLockedToJob = usesGeneratedPayload || (!isGeneration && selectedMethod.id !== 'sfwmark' && Boolean(sourceJobId))
  const messageFieldLabel = repositorySpec ? 'Repository-generated watermark' : selectedMethod.id === 'sfwmark'
    ? 'Watermark variant'
    : selectedMethod.id === 'gaussian-shannon'
      ? messageLockedToJob ? 'Embedded message (256 bits; linked job)' : isGeneration ? 'Message (256 binary bits)' : 'Expected message (256 binary bits)'
      : selectedMethod.id === 'lawa'
        ? messageLockedToJob ? 'Embedded message (48 bits; linked job)' : isGeneration ? 'Message (48 binary bits)' : 'Expected message (48 binary bits)'
        : selectedMethod.id === 'gaussian-shading'
          ? 'Watermark bits'
          : 'PRC codeword (repository-generated)'

  useEffect(() => {
    const nextSubmethod = selectedMethod.submethods[0]
    setSubmethodId(nextSubmethod.id)
    setMessage(nextSubmethod.defaultMessage)
    setWorkflowId(nextSubmethod.workflows[0].id)
  }, [methodId, selectedMethod])

  useEffect(() => {
    if (isGeneration) return
    const controller = new AbortController()
    async function loadJobs() {
      try {
        const query = new URLSearchParams({ method: selectedMethod.id, submethod: selectedSubmethod.id })
        const response = await fetch(`${apiBase}/jobs?${query.toString()}`, { signal: controller.signal })
        if (!response.ok) return
        const payload = await response.json()
        if (!controller.signal.aborted) setJobs(payload.jobs ?? [])
      } catch {
        if (!controller.signal.aborted) setJobs([])
      }
    }
    void loadJobs()
    return () => controller.abort()
  }, [isGeneration, selectedMethod.id, selectedSubmethod.id])

  useEffect(() => () => {
    uploadReaderRef.current?.abort()
  }, [])

  useEffect(() => {
    if (!selectedSubmethod.workflows.some((workflow) => workflow.id === workflowId)) setWorkflowId(selectedSubmethod.workflows[0].id)
  }, [selectedSubmethod, workflowId])

  function selectSubmethod(id: string) {
    const next = selectedMethod.submethods.find((submethod) => submethod.id === id)
    if (!next) return
    setSubmethodId(id)
    setMessage(next.defaultMessage)
    setWorkflowId(next.workflows[0].id)
    clearAnalysisContext()
    resetResult(next.workflows[0].id)
  }

  function selectMethod(id: MethodId) {
    const nextMethod = methods.find((method) => method.id === id) ?? methods[0]
    setCategoryId(nextMethod.categoryId)
    setMethodId(id)
    setSubmethodId(nextMethod.submethods[0].id)
    setMessage(nextMethod.submethods[0].defaultMessage)
    setRepositoryOptions(defaultRepositoryOptions(id))
    setWorkflowId(nextMethod.submethods[0].workflows[0].id)
    clearAnalysisContext()
    resetResult(nextMethod.submethods[0].workflows[0].id)
  }

  function clearAnalysisContext() {
    uploadReaderRef.current?.abort()
    setCustomUpload(false)
    runTokenRef.current += 1
    setUploadedImage(null)
    setUploadName('No image selected')
    setSourceJobId(null)
    setSelectedJobId('')
    setJobs([])
  }

  function selectCategory(id: CategoryId) {
    if (id === categoryId) return
    const firstMethod = methods.find((method) => method.categoryId === id)
    if (firstMethod) selectMethod(firstMethod.id)
  }

  function changeSelectorView(view: 'categories' | 'methods', id?: CategoryId) {
    if (id) selectCategory(id)
    setSelectorView(view)
    requestAnimationFrame(() => {
      const target = view === 'methods' ? categoryBackRef.current : categoryButtonRefs.current[categoryId]
      target?.focus({ preventScroll: true })
    })
  }

  function selectWorkflow(id: WorkflowId) {
    const next = selectedSubmethod.workflows.find((workflow) => workflow.id === id)
    if (!next || !next.available) return
    setWorkflowId(id)
    resetResult(id)
  }

  function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    uploadReaderRef.current?.abort()
    const reader = new FileReader()
    uploadReaderRef.current = reader
    reader.onload = () => {
      setUploadedImage(String(reader.result))
      setUploadName(file.name)
      setCustomUpload(true)
      resetResult(selectedWorkflow.id)
    }
    reader.readAsDataURL(file)
    event.target.value = ''
  }

  async function runBackendJob(workflow: WorkflowId = selectedWorkflow.id) {
    const workflowSpec = selectedSubmethod.workflows.find((item) => item.id === workflow) ?? selectedWorkflow
    if (!workflowSpec.available || !workflowSpec.backendWorkflow) return
    if (requestInFlightRef.current) return
    requestInFlightRef.current = true
    const runToken = ++runTokenRef.current
    const requestMethodId = methodId
    setResult({ workflow, status: 'running', title: `Running ${workflowSpec.label.toLowerCase()}`, score: 0, bits: '--', runtime: '--', notes: 'Waiting for the repository result.', imageUrl: null })

    try {
      const endpoint = workflowSpec.backendWorkflow === 'detect' ? '/detect' : '/watermark/generate'
      const response = await fetch(`${apiBase}${endpoint}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          method: methodId,
          submethodId: selectedSubmethod.id,
          analysisMode: workflow,
          prompt,
          message,
          seed: selectedMethod.id === 'sfwmark' ? 42 : seed,
          imageName: uploadName === 'No image selected' ? null : uploadName,
          imageDataUrl: uploadedImage,
          sourceJobId,
          options: repositoryOptions,
        }),
      })

      if (runToken !== runTokenRef.current) return
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}))
        if (runToken !== runTokenRef.current) return
        const errorText = errorPayload.error ?? `Backend returned ${response.status}`
        setResult({ status: 'done', workflow, title: 'Backend request failed', score: 0, bits: '--', runtime: '--', notes: errorText, errorDetails: errorText, imageUrl: null, isError: true })
        return
      }

      const payload = await response.json()
      if (runToken !== runTokenRef.current || requestMethodId !== methodId) return
      const backendResult = payload.result as BackendResult
      const backendImageUrl = backendResult.image_url ? `${fileBase}${backendResult.image_url}` : null
      const backendJobId = backendResult.job_id ?? null
      setResult({
        status: 'done',
        workflow,
        title: resultTitle(selectedMethod.name, workflow, backendResult),
        score: backendResult.detection_score,
        bits: backendResult.recovered_payload,
        bitErrorRate: typeof backendResult.raw?.bit_error_rate === 'number' ? `${(backendResult.raw.bit_error_rate * 100).toFixed(2)}%` : undefined,
        runtime: backendResult.runtime,
        notes: resultSummary(workflow, backendResult, backendImageUrl),
        errorDetails: backendResult.status === 'failed' || backendResult.status === 'setup_required' || backendResult.status === 'unsupported'
          ? [
              `${selectedMethod.name} · ${workflowSpec.label} · ${backendResult.status}`,
              backendResult.recovered_payload,
              backendResult.raw?.summary,
              ...(backendResult.logs ?? []),
            ].filter((line, index, lines): line is string => Boolean(line) && lines.indexOf(line) === index).join('\n\n')
          : undefined,
        raw: backendResult.raw,
        imageUrl: backendImageUrl,
        isError: backendResult.status === 'failed' || backendResult.status === 'setup_required' || backendResult.status === 'unsupported',
        jobId: backendJobId,
        jobNumber: backendResult.raw?.job_number ?? null,
      })
      if (backendImageUrl) {
        setCustomUpload(false)
        setUploadedImage(backendImageUrl)
        setUploadName('Generated watermarked image')
        setSourceJobId(backendJobId)
        setSelectedJobId(backendJobId ?? '')
      }
    } catch (error) {
      if (runToken !== runTokenRef.current) return
      const errorText = `${error instanceof Error ? error.message : 'Network error'}. Make sure backend is running on ${apiBase}.`
      setResult({ status: 'done', workflow, title: 'Backend not reachable', score: 0, bits: '--', runtime: '--', notes: errorText, errorDetails: errorText, imageUrl: null, isError: true })
    } finally {
      requestInFlightRef.current = false
    }
  }

  function analyzeGeneratedImage(nextWorkflow: WorkflowId) {
    if (!uploadedImage || !sourceJobId) return
    setWorkflowId(nextWorkflow)
    void runBackendJob(nextWorkflow)
  }

  function detectGeneratedImage() {
    analyzeGeneratedImage(selectedMethod.id === 'prc-watermark' ? 'detect' : 'verify')
  }

  function selectPreviousJob(jobId: string) {
    setSelectedJobId(jobId)
    const job = jobs.find((item) => item.job_id === jobId)
    setSourceJobId(job?.job_id ?? null)
    if (!job) return
    if (!customUpload) {
      setUploadedImage(`${fileBase}${job.image_url}`)
      setUploadName(`Previous ${job.label}`)
    }
    resetResult(selectedWorkflow.id)
    const matchingSubmethod = selectedMethod.submethods.find((submethod) => submethod.id === job.submethod_id)
    if (matchingSubmethod) {
      setSubmethodId(matchingSubmethod.id)
      setMessage(job.message || matchingSubmethod.defaultMessage)
    }
  }

  function resultTitle(methodName: string, workflow: WorkflowId, backendResult: BackendResult) {
    const workflowLabel = workflow === 'generate' ? 'generation' : selectedSubmethod.workflows.find((item) => item.id === workflow)?.label.toLowerCase() ?? 'analysis'
    if (backendResult.status === 'setup_required') return `${methodName} ${workflowLabel} needs runtime setup`
    if (backendResult.status === 'unsupported') return `${methodName} ${workflowLabel} unavailable`
    if (backendResult.status === 'failed') return `${methodName} ${workflowLabel} failed`
    return `${methodName} ${workflowLabel} complete`
  }

  function resultSummary(workflow: WorkflowId, backendResult: BackendResult, imageUrl: string | null) {
    if (backendResult.status === 'failed' || backendResult.status === 'setup_required' || backendResult.status === 'unsupported') return backendResult.recovered_payload || 'The backend could not complete this run.'
    if (workflow === 'generate') return imageUrl ? `${selectedSubmethod.name} watermarked image generated and ready for analysis.` : `${selectedSubmethod.name} generation completed.`
    const raw = backendResult.raw
    if (raw?.summary) return raw.summary
    if (workflow === 'verify' && selectedMethod.id === 'sfwmark' && raw) return `Verification distance against the ground-truth pattern: ${typeof raw.verification_distance === 'number' ? raw.verification_distance.toFixed(4) : 'recorded'}. The original repo uses this distance for ROC evaluation.`
    if (workflow === 'verify' && selectedMethod.id === 'gaussian-shading' && raw) return `Recovered ${raw.mark_length ?? 'the'} watermark bits with ${typeof raw.bit_accuracy === 'number' ? `${(raw.bit_accuracy * 100).toFixed(2)}%` : 'recorded'} accuracy. Detection and traceability use the repository's separate FPR-derived thresholds.`
    if (workflow === 'detect' && selectedMethod.id === 'prc-watermark' && raw) return `PRC Detect returned ${raw.detection_result ? 'watermark detected' : 'watermark not detected'} using the target false-positive rate.`
    if (workflow === 'decode' && selectedMethod.id === 'prc-watermark' && raw) return `PRC Decode returned ${raw.decoding_result ? 'decode valid' : 'decode invalid'} for the linked decoding key.`
    if (workflow === 'identify' && raw) return `Closest candidate is pattern ${raw.predicted_index}; identification was ${raw.identified ? 'correct' : 'incorrect'}. The ground-truth key is used only to score the result.`
    if (workflow === 'verify') return `Verification is represented by the repository's extraction step. Recovered bits are compared with the supplied message and reported as bit error rate or bit accuracy.`
    return backendResult.recovered_payload || 'Extraction completed.'
  }

  function resetRun() {
    resetResult(selectedWorkflow.id)
  }

  function resetResult(nextWorkflow: WorkflowId) {
    setResult({ status: 'idle', workflow: nextWorkflow, title: 'Ready', score: 0, bits: '--', runtime: '--', notes: 'Choose a method, submethod, and workflow, then run the repository-backed action.', imageUrl: null, jobId: null, jobNumber: null, raw: undefined })
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="The Watermarking Library navigation">
        <div className="brand">
          <div className="brand-mark"><BookOpen size={22} strokeWidth={2.1} aria-hidden="true" /></div>
          <div><p className="eyebrow">Latent domain methods</p><h1>The Watermarking Library</h1><span className="owner-name">Chern Ze Hou</span></div>
        </div>
        <div className="sidebar-context"><strong>{selectedMethod.name}</strong><span>{selectedSubmethod.name} · {selectedWorkflow.label}</span></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <h2>Watermark Method Catalogue</h2>
          <span className="catalogue-total">{categories.length} categories · {methods.length} methods</span>
        </header>

        <div className="catalog-selector">
          <div className={`selector-stage ${selectorView === 'categories' ? 'is-active' : ''}`} inert={selectorView !== 'categories'} aria-hidden={selectorView !== 'categories'}>
            <nav className="category-grid" aria-label="Watermark categories">
              {categories.map((category, index) => {
                const count = methods.filter((method) => method.categoryId === category.id).length
                const CategoryIcon = [Waves, Aperture, Layers, SlidersHorizontal, Activity][index]
                return <button ref={(node) => { categoryButtonRefs.current[category.id] = node }} className="category-button" key={category.id} onClick={() => changeSelectorView('methods', category.id)} style={{ '--category-color': category.color } as CSSProperties} type="button">
                  <span className="category-icon"><CategoryIcon aria-hidden="true" size={20} /></span>
                  <span className="category-copy"><strong>{category.name} <span className="category-count">({count} {count === 1 ? 'Method' : 'Methods'})</span></strong><small>{category.detail}</small></span>
                </button>
              })}
            </nav>
          </div>
          <div className={`selector-stage ${selectorView === 'methods' ? 'is-active' : ''}`} inert={selectorView !== 'methods'} aria-hidden={selectorView !== 'methods'}>
              <div className="category-heading"><button ref={categoryBackRef} className="category-back" onClick={() => changeSelectorView('categories')} title="Back to categories" aria-label="Back to categories" type="button"><ArrowLeft aria-hidden="true" size={19} /></button><div><span>Category</span><h3>{selectedCategory.name}</h3></div><span>{categoryMethods.length} {categoryMethods.length === 1 ? 'method' : 'methods'}</span></div>
              <section className="method-grid" aria-label={`${selectedCategory.name} methods`}>
                {categoryMethods.map((method) => <button aria-pressed={method.id === selectedMethod.id} className={`method-card ${method.id === selectedMethod.id ? 'selected' : ''}`} key={method.id} onClick={() => selectMethod(method.id)} style={{ '--method-color': method.color } as CSSProperties} type="button"><span className="method-token">{method.shortName}</span><span className="method-copy"><strong>{method.name}</strong><small>{method.category}</small></span></button>)}
              </section>
          </div>
        </div>

        <section className="method-navigation" aria-label={`${selectedMethod.name} submethods and workflows`}>
          <div className="navigation-group"><div className="navigation-label"><span>Submethod</span></div><div className="submethod-tabs">{selectedMethod.submethods.map((submethod) => <button aria-pressed={submethod.id === selectedSubmethod.id} className={submethod.id === selectedSubmethod.id ? 'active' : ''} key={submethod.id} onClick={() => selectSubmethod(submethod.id)} type="button">{submethod.name}</button>)}</div></div>
          <div className="navigation-group"><div className="navigation-label"><span>Repository action</span></div><div className="workflow-tabs">{selectedSubmethod.workflows.filter((workflow) => workflow.available).map((workflow) => <button aria-pressed={workflow.id === selectedWorkflow.id} className={`${workflow.id === selectedWorkflow.id ? 'active' : ''} ${workflow.available ? '' : 'disabled'}`} disabled={!workflow.available} key={workflow.id} onClick={() => selectWorkflow(workflow.id)} title={workflow.available ? workflow.label : workflow.unavailableReason ?? `${workflow.label} is not implemented by this repository`} type="button">{workflow.id === 'generate' ? <Sparkles size={15} /> : workflow.id === 'identify' ? <Search size={15} /> : <ShieldCheck size={15} />}{workflow.label}</button>)}</div></div>
        </section>

        <section className="main-grid">
          <div className="control-panel">
            <div className="control-heading-row"><div className="control-title"><SlidersHorizontal size={18} /><h3>{selectedWorkflow.label}</h3></div>
              {repositorySpec && <a className="repository-link" href={repositorySpec.repo_url} target="_blank" rel="noreferrer">Official repository <ExternalLink aria-hidden="true" size={17} /></a>}
              <p className="heading-description control-description">{selectedWorkflow.description}</p>
            </div>

            {isGeneration ? <label className="field"><span>Prompt</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} /></label> : null}
            {needsImage ? <>
              <label className="upload-zone primary-upload"><input accept="image/*" onChange={handleUpload} type="file" /><ImageUp size={20} /><span>{uploadName}</span></label>
              <div className={`source-job-note ${sourceJobId ? 'linked' : ''}`}><strong>{sourceJobId ? `Linked generation job: ${sourceJobId}` : 'No generation job linked'}</strong><span>{isSfwAnalysis ? 'SFWMark analysis uses the saved pattern bank and key associated with a generated job.' : requiresSourceKey ? `${selectedMethod.name} analysis requires the state and configuration saved with a compatible generation job.` : 'A linked job is optional; analysis requires matching model and message settings.'}</span></div>
              <label className="field previous-job-field"><span>Linked generation job</span><select aria-label="Linked generation job" value={selectedJobId} onChange={(event) => selectPreviousJob(event.target.value)}><option value="">Select a saved {selectedSubmethod.name} job</option>{jobs.map((job) => <option key={job.job_id} value={job.job_id}>{job.label} · {job.prompt || job.job_id}</option>)}</select></label>
              {sourceJobId && uploadedImage ? <div className="previous-job-preview"><KeyRound size={18} aria-hidden="true" /><div><strong>{jobs.find((job) => job.job_id === sourceJobId)?.label ?? `Job ${sourceJobId}`}</strong><span>{jobs.find((job) => job.job_id === sourceJobId)?.prompt ?? 'Selected watermarked image'}</span></div></div> : null}
            </> : null}

            <div className="field-row">
              {selectedSubmethod.messageMode === 'generated' || selectedSubmethod.messageMode === 'variant' ? <div className="payload-summary"><span>Payload</span><strong>{selectedSubmethod.payload}</strong></div> : <label className={`field ${selectedMethod.id === 'gaussian-shannon' ? 'message-field' : ''}`}><span>{messageFieldLabel}</span>{selectedMethod.id === 'gaussian-shannon' ? <textarea className="message-textarea" rows={6} value={message} onChange={(event) => setMessage(event.target.value.replace(/\s/g, ''))} disabled={messageLockedToJob} readOnly={messageLockedToJob} spellCheck={false} /> : <input value={message} onChange={(event) => setMessage(event.target.value)} disabled={messageLockedToJob} readOnly={messageLockedToJob} />}</label>}
              <label className="field small-field"><span>{selectedMethod.id === 'sfwmark' ? 'Seed (fixed upstream)' : 'Seed'}</span><input value={selectedMethod.id === 'sfwmark' ? 42 : seed} onChange={(event) => setSeed(Number(event.target.value))} type="number" disabled={!isGeneration || selectedMethod.id === 'sfwmark'} /></label>
            </div>

            {isGeneration && selectedMethod.id === 'gaussian-shading' ? <div className="option-grid" aria-label="Gaussian Shading repository options">
              <label className="field"><span>Channel copies</span><select value={repositoryOptions.channel_copy} onChange={(event) => setRepositoryOptions((current) => ({ ...current, channel_copy: Number(event.target.value) }))}><option value={1}>1</option><option value={2}>2</option><option value={4}>4</option></select></label>
              <label className="field"><span>Spatial copies</span><select value={repositoryOptions.hw_copy} onChange={(event) => setRepositoryOptions((current) => ({ ...current, hw_copy: Number(event.target.value) }))}>{[1, 2, 4, 8, 16, 32, 64].map((value) => <option key={value} value={value}>{value} x {value}</option>)}</select></label>
              <label className="field"><span>Target FPR</span><input min="0.000000001" max="0.1" step="0.000001" type="number" value={repositoryOptions.fpr} onChange={(event) => setRepositoryOptions((current) => ({ ...current, fpr: Number(event.target.value) }))} /></label>
              <label className="field"><span>User population</span><input min="1" step="1" type="number" value={repositoryOptions.user_number} onChange={(event) => setRepositoryOptions((current) => ({ ...current, user_number: Number(event.target.value) }))} /></label>
              <label className="field"><span>Diffusion steps</span><input min="1" max="200" step="1" type="number" value={repositoryOptions.inference_steps} onChange={(event) => setRepositoryOptions((current) => ({ ...current, inference_steps: Number(event.target.value) }))} /></label>
            </div> : null}

            {isGeneration && selectedMethod.id === 'prc-watermark' ? <div className="option-grid" aria-label="PRC-Watermark repository options">
              <label className="field"><span>Target FPR</span><input min="0.000000001" max="0.1" step="0.00001" type="number" value={repositoryOptions.fpr} onChange={(event) => setRepositoryOptions((current) => ({ ...current, fpr: Number(event.target.value) }))} /></label>
              <label className="field"><span>Parity sparsity t</span><input min="2" max="10" step="1" type="number" value={repositoryOptions.prc_t} onChange={(event) => setRepositoryOptions((current) => ({ ...current, prc_t: Number(event.target.value) }))} /></label>
              <label className="field"><span>Posterior variance</span><input min="0.1" max="10" step="0.1" type="number" value={repositoryOptions.posterior_variance} onChange={(event) => setRepositoryOptions((current) => ({ ...current, posterior_variance: Number(event.target.value) }))} /></label>
              <label className="field"><span>Diffusion steps</span><input min="1" max="200" step="1" type="number" value={repositoryOptions.inference_steps} onChange={(event) => setRepositoryOptions((current) => ({ ...current, inference_steps: Number(event.target.value) }))} /></label>
            </div> : null}

            {isGeneration && repositorySpec && <div className="option-grid" aria-label={`${selectedMethod.name} repository options`}>
              {Object.entries(repositorySpec.options).map(([key, spec]) => <label className={`field ${spec.type === 'toggle' ? 'binary-option' : ''}`} key={key}><span>{spec.label}</span>{spec.type === 'toggle' ? <input type="checkbox" checked={Boolean(repositoryOptions[key])} onChange={(event) => setRepositoryOptions((current) => ({ ...current, [key]: Number(event.target.checked) }))} /> : spec.type === 'select' ? <select value={repositoryOptions[key]} onChange={(event) => setRepositoryOptions((current) => ({ ...current, [key]: Number(event.target.value) }))}>{spec.choices!.map((value) => <option key={value} value={value}>{value}</option>)}</select> : <input type="number" min={spec.min} max={spec.max} step={spec.step} value={repositoryOptions[key]} onChange={(event) => setRepositoryOptions((current) => ({ ...current, [key]: Number(event.target.value) }))} />}</label>)}
            </div>}

            <div className="form-actions">
              <button className="reset-button" onClick={resetRun} type="button" title="Clear results" aria-label="Clear results"><RotateCcw size={17} /></button>
              <button className="primary-button" disabled={result.status === 'running' || !selectedWorkflow.available || (!isGeneration && (!uploadedImage || (requiresSourceKey && !sourceJobId)))} onClick={() => runBackendJob()} type="button"><Play size={17} />{result.status === 'running' ? 'Running...' : `Run ${selectedWorkflow.label}`}</button>
            </div>
          </div>

          <div className="preview-panel"><div className="section-heading"><Aperture size={18} /><div><h3>{isGeneration ? 'Generated Image' : 'Analysis Image'}</h3><p className="heading-description">{isGeneration ? 'Only the watermarked output is shown.' : 'The image supplied to this repository workflow.'}</p></div></div><div className={`image-stage ${uploadedImage ? 'has-image' : ''}`}>{uploadedImage ? <img src={uploadedImage} alt="Generated or uploaded watermarked preview" /> : <div className="image-placeholder"><ImageUp size={30} strokeWidth={1.25} /><span>{isGeneration ? 'No generated image yet' : 'No image selected'}</span></div>}</div></div>

          <section className="implementation-panel" aria-label={`${selectedMethod.name} explanation`} style={{ '--method-color': selectedMethod.color } as CSSProperties}>
            <div className="implementation-summary">
              <div><span>Selected implementation</span><strong>{selectedSubmethod.name}</strong><p>{selectedSubmethod.description}</p></div>
              <div><span>Payload and backend behavior</span><strong>{selectedSubmethod.payload}</strong><p>{selectedSubmethod.backendBehavior ?? selectedMethod.mechanism}</p></div>
            </div>
            <details className="technical-details" key={`${methodId}-${submethodId}`}><summary><ChevronDown size={16} />Method reference</summary>
            <div className="workflow-contract" aria-label={`${selectedWorkflow.label} inputs and outputs`}><div><span>Needs</span><ul>{selectedWorkflow.inputs.map((item) => <li key={item}>{item}</li>)}</ul></div><div><span>Returns</span><ul>{selectedWorkflow.outputs.map((item) => <li key={item}>{item}</li>)}</ul></div><div><span>Repository context</span><p>{selectedWorkflow.source}</p></div></div>
            <div className="repo-defaults" aria-label="Website defaults"><strong>Website defaults</strong>{selectedSubmethod.repoDefaults.map((item) => <span key={item}>{item}</span>)}</div>
            {selectedSubmethod.upstreamDefaults && <div className="upstream-reference"><strong>Upstream reference</strong><p>{selectedSubmethod.upstreamDefaults}</p>{selectedSubmethod.sourceUrl && <a href={selectedSubmethod.sourceUrl} target="_blank" rel="noreferrer">Reviewed repository source</a>}</div>}
            </details>
            <div className="process-map">
              <div className="process-map-heading"><h3>{selectedSubmethod.name} Processes</h3></div>
              <div className="process-rows">{(selectedSubmethod.processes ?? selectedMethod.processes).map((process) => <div aria-current={process.workflow === selectedWorkflow.id ? 'step' : undefined} className={`process-row ${process.workflow === selectedWorkflow.id ? 'selected' : ''}`} key={process.workflow}><div className="process-label"><strong>{process.label} Flow</strong></div><div className="workflow-chain" aria-label={`${selectedMethod.name} ${process.label} flow`}>{process.steps.map((step, index, steps) => <div className="workflow-item" key={step}><span className="workflow-step">{step}</span>{index < steps.length - 1 ? <ArrowRight className="workflow-arrow" aria-hidden="true" size={16} /> : null}</div>)}</div></div>)}</div>
            </div>
          </section>

          <div className="result-panel"><div className="section-heading"><Activity size={18} /><div><h3>Results</h3><p className="heading-description">Repository output for the selected action.</p></div></div><div className={`status-strip ${result.status} ${result.isError ? 'error' : ''}`}>{result.isError ? <CircleAlert size={18} /> : result.status === 'running' ? <LoaderCircle className="spinner" size={18} /> : result.status === 'done' ? <CheckCircle2 size={18} /> : <Gauge size={18} />}<span>{result.title}</span></div>
            <div className="metric-grid">{repositorySpec && result.workflow !== 'generate' ? <>{(result.raw?.metrics ?? [{ label: 'Repository result', value: '--' }]).map((metric) => <div className="metric" key={metric.label}><span>{metric.label}</span><strong>{typeof metric.value === 'boolean' ? metric.value ? 'Yes' : 'No' : metric.value}</strong></div>)}</> : result.workflow === 'generate' ? <><div className="metric"><span>Generation job</span><strong>{result.jobNumber ? `Job #${result.jobNumber}` : result.jobId ? `Job ${result.jobId}` : '--'}</strong></div><div className="metric"><span>Submethod</span><strong>{selectedSubmethod.name}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Output</span><strong>{result.imageUrl ? 'Watermarked image' : '--'}</strong></div></> : result.workflow === 'verify' && selectedMethod.id === 'sfwmark' ? <><div className="metric"><span>Expected-pattern distance</span><strong>{typeof result.raw?.verification_distance === 'number' ? result.raw.verification_distance.toFixed(4) : '--'}</strong></div><div className="metric"><span>Expected key</span><strong>{result.raw?.key_index ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Repo metric</span><strong>ROC distance</strong></div></> : result.workflow === 'verify' && selectedMethod.id === 'gaussian-shading' ? <><div className="metric"><span>Detection</span><strong>{result.raw?.detected === undefined ? '--' : result.raw.detected ? 'Detected' : 'Not detected'}</strong></div><div className="metric"><span>Traceability</span><strong>{result.raw?.traceable === undefined ? '--' : result.raw.traceable ? 'Passed' : 'Not passed'}</strong></div><div className="metric"><span>Bit accuracy</span><strong>{typeof result.raw?.bit_accuracy === 'number' ? `${(result.raw.bit_accuracy * 100).toFixed(2)}%` : '--'}</strong></div><div className="metric"><span>Bit error rate</span><strong>{result.bitErrorRate ?? '--'}</strong></div></> : isPrcAnalysis ? isPrcDetect ? <><div className="metric"><span>Detect result</span><strong>{result.raw?.detection_result === undefined ? '--' : result.raw.detection_result ? 'Detected' : 'Not detected'}</strong></div><div className="metric"><span>Target FPR</span><strong>{result.raw?.fpr ?? '--'}</strong></div><div className="metric"><span>Codeword length</span><strong>{result.raw?.codeword_length ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div></> : <><div className="metric"><span>Decode validity</span><strong>{result.raw?.decoding_result === undefined ? '--' : result.raw.decoding_result ? 'Valid' : 'Invalid'}</strong></div><div className="metric"><span>Target FPR</span><strong>{result.raw?.fpr ?? '--'}</strong></div><div className="metric"><span>Codeword length</span><strong>{result.raw?.codeword_length ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div></> : result.workflow === 'identify' ? <><div className="metric"><span>Identification</span><strong>{result.raw?.identified === undefined ? '--' : result.raw.identified ? 'Correct' : 'Incorrect'}</strong></div><div className="metric"><span>Predicted key</span><strong>{result.raw?.predicted_index ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Candidate bank</span><strong>2048 patterns</strong></div></> : <><div className="metric"><span>Bit error rate</span><strong>{result.bitErrorRate ?? '--'}</strong></div><div className="metric"><span>Recovered output</span><strong>{result.bits}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Payload</span><strong>{selectedSubmethod.payload}</strong></div></>}</div>
            {repositorySpec && result.workflow === 'decode' && result.bits !== '--' && !result.isError && <pre className="recovered-bits" aria-label="Recovered watermark bits">{result.bits}</pre>}
            {result.raw?.mask_url && <figure className="tamper-result"><img src={`${fileBase}${result.raw.mask_url}`} alt="Predicted tamper localization mask" /><figcaption>Predicted tamper mask</figcaption></figure>}
            {result.workflow === 'verify' && selectedMethod.id === 'gaussian-shannon' && result.raw ? <div className="repository-result-note"><div><span>Repository decoding</span><strong>{result.raw.coding ?? selectedSubmethod.name} · {result.raw.redundancy ?? '--'} redundant copies · {result.raw.num_elements ?? '--'} extracted symbols</strong></div><div><span>Decision rule</span><strong>{result.raw.decoder ?? 'majority vote'}</strong></div><div><span>Bit accuracy</span><strong>{result.score}% bit accuracy</strong></div></div> : null}
            {result.workflow === 'verify' && selectedMethod.id === 'gaussian-shading' && result.raw ? <div className="repository-result-note"><div><span>Detection threshold</span><strong>{typeof result.raw.tau_detection === 'number' ? result.raw.tau_detection.toFixed(4) : '--'} accuracy at FPR {result.raw.fpr ?? '--'}</strong></div><div><span>Traceability threshold</span><strong>{typeof result.raw.tau_traceability === 'number' ? result.raw.tau_traceability.toFixed(4) : '--'} across {result.raw.user_number ?? '--'} users</strong></div><div><span>Recovered watermark</span><strong>{result.raw.mark_length ?? '--'} bits · {result.raw.channel_copy ?? '--'} channel copies · {result.raw.hw_copy ?? '--'} x {result.raw.hw_copy ?? '--'} spatial copies</strong></div></div> : null}
            {isPrcAnalysis && result.raw ? <div className="repository-result-note"><div><span>Repository operation</span><strong>{isPrcDetect ? 'Detect' : 'Decode'}</strong></div><div><span>Repository decoder</span><strong>{result.raw.decoder ?? (isPrcDetect ? 'Detect' : 'Decode')}</strong></div><div><span>Decision rule</span><strong>{result.raw.decision_rule ?? (isPrcDetect ? 'Detect' : 'Decode validity')}</strong></div><div><span>PRC parameters</span><strong>n = {result.raw.codeword_length ?? '--'} · t = {result.raw.prc_t ?? '--'} · variance = {result.raw.posterior_variance ?? '--'}</strong></div><div><span>Posterior and key</span><strong>{result.raw.posterior_length ?? '--'} values · noise rate {result.raw.noise_rate ?? '--'} · {result.raw.test_bit_count ?? '--'} test bits</strong></div><div><span>Decode limit</span><strong>{result.raw.max_bp_iter ?? '--'} BP iterations{isPrcDetect ? ' (not used by Detect)' : ''}</strong></div><div><span>Message output</span><strong>{result.raw.message_available ? 'Recovered message' : 'No user message; validity only'}</strong></div><div><span>Inversion</span><strong>Order {result.raw.inversion_order ?? '--'} · empty prompt</strong></div></div> : null}
            <div className="api-note"><KeyRound size={18} /><p>{result.notes}</p></div>
            {result.isError && result.errorDetails ? <section className="error-details" aria-label="Full error details">
              <div className="error-details-heading"><strong>Full error details</strong><button className="copy-error-button" onClick={async () => {
                try {
                  await navigator.clipboard.writeText(result.errorDetails ?? '')
                  setCopiedErrorDetails(true)
                  window.setTimeout(() => setCopiedErrorDetails(false), 1800)
                } catch {
                  setCopiedErrorDetails(false)
                }
              }} type="button" title="Copy full error details" aria-label="Copy full error details">{copiedErrorDetails ? <Check size={16} /> : <Copy size={16} />}{copiedErrorDetails ? 'Copied' : 'Copy'}</button></div>
              <pre>{result.errorDetails}</pre>
            </section> : null}
            {isGeneration && uploadedImage && sourceJobId && !result.isError ? <div className="result-actions">{repositorySpec ? selectedSubmethod.workflows.filter((item) => item.available && item.id !== 'generate').map((item) => <button className="secondary-button" key={item.id} disabled={result.status === 'running'} onClick={() => analyzeGeneratedImage(item.id)} type="button"><Search size={18} />{item.label}</button>) : selectedMethod.id === 'prc-watermark' ? <><button className="secondary-button" disabled={result.status === 'running'} onClick={() => analyzeGeneratedImage('detect')} type="button"><Search size={18} />Run Detect</button><button className="secondary-button" disabled={result.status === 'running'} onClick={() => analyzeGeneratedImage('decode')} type="button"><ShieldCheck size={18} />Run Decode</button></> : <button className="secondary-button" onClick={detectGeneratedImage} type="button"><ShieldCheck size={18} />Verify this image</button>}{result.imageUrl ? <a className="download-link" href={result.imageUrl} download><Download size={18} />Download watermarked image</a> : null}</div> : null}
          </div>
        </section>
      </section>
    </main>
  )
}

export default App
