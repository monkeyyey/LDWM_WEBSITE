import {
  Activity,
  Aperture,
  Binary,
  CheckCircle2,
  Cloud,
  Gauge,
  ImageUp,
  KeyRound,
  Play,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Waves,
} from 'lucide-react'
import { type ChangeEvent, useEffect, useMemo, useState } from 'react'
import './App.css'

type MethodId = 'sfwmark' | 'gaussian-shannon' | 'lawa'
type Mode = 'detect' | 'generate'

type Method = {
  id: MethodId
  name: string
  shortName: string
  category: string
  mechanism: string
  bestFor: string
  payload: string
  robustness: number
  quality: number
  latency: string
  color: string
  messageLabel: string
  defaultMessage: string
  repoDefaults: string[]
  attacks: string[]
}

type Result = {
  status: 'idle' | 'running' | 'done'
  title: string
  score: number
  bits: string
  runtime: string
  notes: string
  imageUrl?: string | null
  isError?: boolean
}

const methods: Method[] = [
  {
    id: 'sfwmark',
    name: 'SFWMark',
    shortName: 'SFW',
    category: 'Fourier latent watermark',
    mechanism: 'Embeds integrity-aware structure into the Fourier space of latent noise.',
    bestFor: 'Robust image provenance under crop, resize, and compression.',
    payload: 'Keyed presence signal',
    robustness: 91,
    quality: 88,
    latency: 'Medium',
    color: '#136f63',
    messageLabel: 'Watermark type',
    defaultMessage: 'HSQR',
    repoDefaults: ['wm_type: HSQR', 'dataset_id: coco | Gustavo | DB1k', 'attacks: JPEG, Diffusion, CC, RC'],
    attacks: ['None', 'JPEG', 'Diffusion', 'Center crop (CC)', 'Random crop (RC)', 'Blur', 'Noise', 'Brightness', 'Contrast'],
  },
  {
    id: 'gaussian-shannon',
    name: 'Gaussian Shannon',
    shortName: 'GS',
    category: 'Communication-code watermark',
    mechanism: 'Treats generation and inversion as a noisy channel with redundant bit recovery.',
    bestFor: 'Recovering exact IDs or short messages after common attacks.',
    payload: 'Message bits',
    robustness: 87,
    quality: 84,
    latency: 'High',
    color: '#7a4f00',
    messageLabel: 'Payload mode',
    defaultMessage: '256-bit zero message',
    repoDefaults: ['model_id: stabilityai/stable-diffusion-2-1', 'message: 256 bits', 'redundancy: 64'],
    attacks: ['None', 'JPEG', 'Gaussian blur', 'Gaussian noise', 'Random crop', 'Random drop', 'Rotate', 'SDEdit'],
  },
  {
    id: 'lawa',
    name: 'LaWa',
    shortName: 'LW',
    category: 'VAE latent watermark',
    mechanism: 'Uses the autoencoder latent pathway and decoder-side behavior for in-generation marks.',
    bestFor: 'Showing a model-integrated latent watermark family.',
    payload: '48-bit watermark',
    robustness: 79,
    quality: 90,
    latency: 'Low',
    color: '#315f9f',
    messageLabel: '48-bit binary message',
    defaultMessage: '110111001110110001000000011101000110011100110101',
    repoDefaults: ['config: configs/SD14_LaWa_inference.yaml', 'message_len: 48', 'SD checkpoint: sd-v1-4.ckpt'],
    attacks: ['None', 'Rotation', 'Center crop', 'Resize', 'Blur', 'JPEG', 'Contrast', 'Brightness', 'Hue', 'Combined'],
  },
]

const seedPreview =
  'linear-gradient(135deg, #f4efe4 0%, #dce9e2 36%, #9eb6c6 68%, #2f3a4a 100%)'
const apiBase =
  import.meta.env.VITE_API_BASE ??
  `${globalThis.location?.protocol ?? 'http:'}//${globalThis.location?.hostname ?? '127.0.0.1'}:8000`

function App() {
  const [mode, setMode] = useState<Mode>('generate')
  const [methodId, setMethodId] = useState<MethodId>('sfwmark')
  const [prompt, setPrompt] = useState('a clean product photo of a ceramic mug on a desk')
  const [message, setMessage] = useState(methods[0].defaultMessage)
  const [seed, setSeed] = useState(42)
  const [strength, setStrength] = useState(68)
  const [attack, setAttack] = useState(methods[0].attacks[0])
  const [uploadName, setUploadName] = useState('No image selected')
  const [uploadedImage, setUploadedImage] = useState<string | null>(null)
  const [result, setResult] = useState<Result>({
    status: 'idle',
    title: 'Ready',
    score: 0,
    bits: '--',
    runtime: '--',
    notes: 'Run a backend job. SFWMark generation requires the AWS CUDA backend to be reachable.',
    imageUrl: null,
  })

  const selectedMethod = useMemo(
    () => methods.find((method) => method.id === methodId) ?? methods[0],
    [methodId],
  )

  useEffect(() => {
    setMessage(selectedMethod.defaultMessage)
    setAttack(selectedMethod.attacks[0])
  }, [selectedMethod])

  function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploadName(file.name)

    const reader = new FileReader()
    reader.onload = () => setUploadedImage(String(reader.result))
    reader.readAsDataURL(file)
  }

  async function runBackendJob() {
    setResult((current) => ({
      ...current,
      status: 'running',
      title: 'Submitting backend job',
      notes: `Calling backend at ${apiBase}.`,
    }))

    try {
      const endpoint = mode === 'detect' ? '/detect' : '/watermark/generate'
      const response = await fetch(`${apiBase}${endpoint}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          method: methodId,
          prompt,
          message,
          seed,
          strength,
          attack,
          imageName: uploadName === 'No image selected' ? null : uploadName,
          imageDataUrl: uploadedImage,
        }),
      })

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}))
        setResult({
          status: 'done',
          title: 'Backend request failed',
          score: 0,
          bits: '--',
          runtime: '--',
          notes: errorPayload.error ?? `Backend returned ${response.status}`,
          imageUrl: null,
          isError: true,
        })
        return
      }

      const payload = await response.json()
      const backendResult = payload.result
      const backendImageUrl = backendResult.image_url ? `${apiBase}${backendResult.image_url}` : null
      setResult({
        status: 'done',
        title: `${selectedMethod.name} backend job complete`,
        score: backendResult.detection_score,
        bits: backendResult.recovered_payload,
        runtime: backendResult.runtime,
        notes: backendResult.logs?.join(' ') ?? 'Backend returned a normalized result.',
        imageUrl: backendImageUrl,
        isError: backendResult.status === 'failed' || backendResult.status === 'setup_required',
      })
      if (backendImageUrl) {
        setUploadedImage(backendImageUrl)
        setUploadName('Generated watermarked image')
      }
      return
    } catch (error) {
      setResult({
        status: 'done',
        title: 'Backend not reachable',
        score: 0,
        bits: '--',
        runtime: '--',
        notes: `${error instanceof Error ? error.message : 'Network error'}. Make sure backend is running on ${apiBase} and AWS security group allows port 8000.`,
        imageUrl: null,
        isError: true,
      })
    }
  }

  function resetRun() {
    setResult({
      status: 'idle',
      title: 'Ready',
      score: 0,
      bits: '--',
      runtime: '--',
      notes: 'Run a backend job. SFWMark generation requires the AWS CUDA backend to be reachable.',
      imageUrl: null,
    })
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Watermark lab navigation">
        <div className="brand">
          <div className="brand-mark">
            <Waves size={21} />
          </div>
          <div>
            <p className="eyebrow">Latent Domain</p>
            <h1>Watermark Lab</h1>
            <span className="owner-name">Chern Ze Hou</span>
          </div>
        </div>

        <nav className="mode-tabs" aria-label="Workflow mode">
          <button className={mode === 'detect' ? 'active' : ''} onClick={() => setMode('detect')} type="button">
            <Upload size={18} />
            Detect Uploaded Image
          </button>
          <button className={mode === 'generate' ? 'active' : ''} onClick={() => setMode('generate')} type="button">
            <Sparkles size={18} />
            Generate Watermarked Image
          </button>
        </nav>

        <div className="deployment">
          <Cloud size={18} />
          <div>
            <strong>Local mock mode</strong>
            <span>Frontend ready, GPU API pending</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Prototype dashboard</p>
            <h2>Generate latent watermarked images and evaluate uploaded outputs</h2>
          </div>
          <div className="run-controls">
            <button className="icon-button" onClick={resetRun} type="button" aria-label="Reset run" title="Reset run">
              <RotateCcw size={18} />
            </button>
            <button className="primary-button" onClick={runBackendJob} type="button">
              <Play size={18} />
              Run
            </button>
          </div>
        </header>

        <section className="method-grid" aria-label="Watermark methods">
          {methods.map((method) => (
            <button
              className={`method-card ${method.id === selectedMethod.id ? 'selected' : ''}`}
              key={method.id}
              onClick={() => setMethodId(method.id)}
              style={{ '--method-color': method.color } as React.CSSProperties}
              type="button"
            >
              <span className="method-token">{method.shortName}</span>
              <span>
                <strong>{method.name}</strong>
                <small>{method.category}</small>
              </span>
            </button>
          ))}
        </section>

        <section className="main-grid">
          <div className="control-panel">
            <div className="section-heading">
              <SlidersHorizontal size={18} />
              <h3>{mode === 'detect' ? 'Detection Workflow' : 'Generation Workflow'}</h3>
            </div>

            {mode === 'generate' ? (
              <label className="field">
                <span>Prompt</span>
                <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} />
              </label>
            ) : (
              <label className="upload-zone primary-upload">
                <input accept="image/*" onChange={handleUpload} type="file" />
                <ImageUp size={20} />
                <span>{uploadName}</span>
              </label>
            )}

            <div className="field-row">
              <label className="field">
                <span>{selectedMethod.messageLabel}</span>
                <input value={message} onChange={(event) => setMessage(event.target.value)} />
              </label>
              <label className="field small-field">
                <span>Seed</span>
                <input value={seed} onChange={(event) => setSeed(Number(event.target.value))} type="number" />
              </label>
            </div>

            <label className="field">
              <span>Embedding strength</span>
              <div className="slider-row">
                <input value={strength} min={10} max={100} onChange={(event) => setStrength(Number(event.target.value))} type="range" />
                <strong>{strength}</strong>
              </div>
            </label>

            <label className="field">
              <span>Optional robustness test</span>
              <select value={attack} onChange={(event) => setAttack(event.target.value)}>
                {selectedMethod.attacks.map((attackName) => (
                  <option key={attackName}>{attackName}</option>
                ))}
              </select>
            </label>

            <div className="repo-defaults" aria-label="Repository defaults">
              {selectedMethod.repoDefaults.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </div>

          <div className="preview-panel">
            <div className="section-heading">
              <Aperture size={18} />
              <h3>Image Preview</h3>
            </div>
            <div className="image-stage" style={{ background: uploadedImage ? '#111827' : seedPreview }}>
              {uploadedImage ? <img src={uploadedImage} alt="Uploaded preview" /> : <div className="latent-grid" />}
              <span className="stage-badge">{mode === 'detect' ? 'detect uploaded image' : 'generate watermark'}</span>
            </div>
            <div className="method-detail">
              <strong>{selectedMethod.mechanism}</strong>
              <p>{selectedMethod.bestFor}</p>
            </div>
          </div>

          <div className="result-panel">
            <div className="section-heading">
              <Activity size={18} />
              <h3>Results</h3>
            </div>

            <div className={`status-strip ${result.status} ${result.isError ? 'error' : ''}`}>
              {result.status === 'done' ? <CheckCircle2 size={18} /> : <Gauge size={18} />}
              <span>{result.title}</span>
            </div>

            <div className="metric-grid">
              <div className="metric">
                <span>Detection score</span>
                <strong>{result.score ? `${result.score}%` : '--'}</strong>
              </div>
              <div className="metric">
                <span>Recovered payload</span>
                <strong>{result.bits}</strong>
              </div>
              <div className="metric">
                <span>Runtime</span>
                <strong>{result.runtime}</strong>
              </div>
              <div className="metric">
                <span>Payload type</span>
                <strong>{selectedMethod.payload}</strong>
              </div>
            </div>

            <div className="quality-bars">
              <div>
                <span><ShieldCheck size={15} /> Robustness</span>
                <progress value={selectedMethod.robustness} max="100" />
              </div>
              <div>
                <span><Binary size={15} /> Image quality</span>
                <progress value={selectedMethod.quality} max="100" />
              </div>
            </div>

            <div className="api-note">
              <KeyRound size={18} />
              <p>{result.notes}</p>
            </div>
          </div>
        </section>
      </section>
    </main>
  )
}

export default App
