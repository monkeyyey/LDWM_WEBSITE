import {
  Activity,
  Aperture,
  ArrowRight,
  CheckCircle2,
  Cloud,
  Download,
  Gauge,
  ImageUp,
  KeyRound,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Waves,
} from 'lucide-react'
import { type ChangeEvent, type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type MethodId = 'sfwmark' | 'gaussian-shannon' | 'lawa'
type WorkflowId = 'generate' | 'verify' | 'identify'
type BackendWorkflow = 'detect' | 'generate'

type WorkflowSpec = {
  id: WorkflowId
  label: string
  description: string
  backendWorkflow: BackendWorkflow | null
  available: boolean
  inputs: string[]
  outputs: string[]
  source: string
  unavailableReason?: string
}

type SubmethodSpec = {
  id: string
  name: string
  description: string
  payload: string
  defaultMessage: string
  repoDefaults: string[]
  workflows: WorkflowSpec[]
}

type Method = {
  id: MethodId
  name: string
  shortName: string
  category: string
  mechanism: string
  bestFor: string
  color: string
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
    wm_type?: string
    model_id?: string
    matched?: boolean
    key_index?: number
    predicted_index?: number
    distance?: number
    bit_error_rate?: number
    bit_accuracy?: number
    analysis_mode?: string
    identified?: boolean
    verification_distance?: number
    source_job_id?: string
    job_number?: number
  }
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
  { id: 'generate', label: 'Generation', description: 'Sample Gaussian latent noise, insert the Fourier watermark, and generate the watermarked image.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', 'HSQR or HSTR', 'Seed'], outputs: ['Watermarked image', '2048-pattern bank', 'Ground-truth key index'], source: 'No source job required' },
  { id: 'verify', label: 'Verification', description: 'Compare the inverted latent with the expected saved watermark pattern.', backendWorkflow: 'detect', available: true, inputs: ['Watermarked image', 'Compatible generation job'], outputs: ['Fourier verification distance'], source: 'Uses the saved pattern and key artifacts' },
  { id: 'identify', label: 'Identification', description: 'Search the candidate pattern bank and return the closest predicted watermark index.', backendWorkflow: 'detect', available: true, inputs: ['Watermarked image', 'Compatible generation job'], outputs: ['Predicted pattern index', 'Correct/incorrect against stored key'], source: 'Searches the saved 2048-pattern bank' },
]

const gaussianWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Encode a 256-bit message into a redundant latent representation before diffusion generation.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', '256-bit binary message', 'Seed'], outputs: ['Watermarked image', 'Coding metadata'], source: 'No source job required' },
  { id: 'verify', label: 'Verification', description: 'Verify the generated image by extracting the 256-bit message; the repository reports bit error rate.', backendWorkflow: 'detect', available: true, inputs: ['Watermarked image', 'Expected 256-bit message', 'Compatible generation job'], outputs: ['Recovered 256 bits', 'Bit error rate'], source: 'DDIM inversion plus Gaussian or LDPC decoding' },
  { id: 'identify', label: 'Identification', description: 'The upstream Gaussian-Shannon repo has no candidate-key identification workflow.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'No candidate-key identification procedure is implemented.' },
]

const lawaWorkflows: WorkflowSpec[] = [
  { id: 'generate', label: 'Generation', description: 'Generate with the LaWa modified decoder and a pretrained 48-bit watermark.', backendWorkflow: 'generate', available: true, inputs: ['Prompt', '48-bit binary message', 'Seed'], outputs: ['Watermarked image'], source: 'No source job required' },
  { id: 'verify', label: 'Verification', description: 'Verify the generated image by extracting the 48-bit message; the repository reports bit accuracy and bit error rate.', backendWorkflow: 'detect', available: true, inputs: ['Watermarked image', 'Expected 48-bit message'], outputs: ['Recovered 48 bits', 'Bit accuracy', 'Bit error rate'], source: 'Pretrained LaWa decoder' },
  { id: 'identify', label: 'Identification', description: 'The upstream LaWa repo has no candidate-key identification workflow.', backendWorkflow: null, available: false, inputs: [], outputs: [], source: 'Unavailable in the upstream repository', unavailableReason: 'LaWa decodes a message but does not search a candidate-key bank.' },
]

const methods: Method[] = [
  {
    id: 'sfwmark',
    name: 'SFWMark',
    shortName: 'SFW',
    category: 'Fourier latent watermark',
    mechanism: 'Embeds a keyed pattern into the Fourier space of Gaussian latent noise before Stable Diffusion generation.',
    bestFor: 'Pattern verification and identification from a generated image after DDIM inversion.',
    color: '#136f63',
    submethods: [
      { id: 'hsqr', name: 'HSQR', description: 'Hermitian-symmetric QR-like Fourier pattern placed in the selected latent frequency region.', payload: 'Keyed pattern index', defaultMessage: 'HSQR', repoDefaults: ['wm_type: HSQR', 'latent: 1 x 4 x 64 x 64', 'Fourier insertion: center slice'], workflows: sfwmarkWorkflow },
      { id: 'hstr', name: 'HSTR', description: 'Hermitian-symmetric tree-ring pattern placed in the selected latent frequency region.', payload: 'Keyed pattern index', defaultMessage: 'HSTR', repoDefaults: ['wm_type: HSTR', 'latent: 1 x 4 x 64 x 64', 'Fourier insertion: center slice'], workflows: sfwmarkWorkflow },
    ],
  },
  {
    id: 'gaussian-shannon',
    name: 'Gaussian Shannon',
    shortName: 'GS',
    category: 'Communication-code watermark',
    mechanism: 'Treats generation and inversion as a noisy channel, using redundancy and coding to recover exact bits.',
    bestFor: 'Message verification and bit error measurement after inversion.',
    color: '#7a4f00',
    submethods: [
      { id: 'gaussian', name: 'Gaussian coding', description: 'Gaussian diffusion of the message with spatial redundancy and majority-vote decoding.', payload: '256-bit message', defaultMessage: '256-bit zero message', repoDefaults: ['encoder: Gaussian', 'message: 256 bits', 'redundancy: 64'], workflows: gaussianWorkflows },
      { id: 'ldpc', name: 'LDPC coding', description: 'LDPC error-correcting code with pseudo-random sign flips, redundancy, and a majority-vote fallback.', payload: '256-bit message', defaultMessage: '256-bit zero message', repoDefaults: ['encoder: LDPC', 'message: 256 bits', 'code rate: 0.25'], workflows: gaussianWorkflows },
    ],
  },
  {
    id: 'lawa',
    name: 'LaWa',
    shortName: 'LW',
    category: 'VAE decoder watermark',
    mechanism: 'Uses a modified Stable Diffusion VAE decoder to carry a pretrained binary watermark during generation.',
    bestFor: '48-bit message verification with the pretrained decoder.',
    color: '#315f9f',
    submethods: [
      { id: 'lawa-48', name: 'LaWa 48-bit', description: 'The repository exposes one pretrained LaWa configuration with a 48-bit message and SD v1.4.', payload: '48-bit message', defaultMessage: '110111001110110001000000011101000110011100110101', repoDefaults: ['config: SD14_LaWa_inference.yaml', 'message_len: 48', 'checkpoint: sd-v1-4.ckpt'], workflows: lawaWorkflows },
    ],
  },
]

const seedPreview = 'linear-gradient(135deg, #f4efe4 0%, #dce9e2 36%, #9eb6c6 68%, #2f3a4a 100%)'
const currentLocation = globalThis.location
const isLocalFrontend = currentLocation?.hostname === 'localhost' || currentLocation?.hostname === '127.0.0.1' || currentLocation?.hostname === ''
const apiBase = import.meta.env.VITE_API_BASE ?? (isLocalFrontend ? `${currentLocation?.protocol ?? 'http:'}//${currentLocation?.hostname ?? '127.0.0.1'}:8000` : `${currentLocation?.origin ?? ''}/api`)
const fileBase = import.meta.env.VITE_FILE_BASE ?? (isLocalFrontend ? apiBase : (currentLocation?.origin ?? ''))

function App() {
  const [workflowId, setWorkflowId] = useState<WorkflowId>('generate')
  const [methodId, setMethodId] = useState<MethodId>('sfwmark')
  const [submethodId, setSubmethodId] = useState(methods[0].submethods[0].id)
  const [prompt, setPrompt] = useState('a clean product photo of a ceramic mug on a desk')
  const [message, setMessage] = useState(methods[0].submethods[0].defaultMessage)
  const [seed, setSeed] = useState(42)
  const [uploadName, setUploadName] = useState('No image selected')
  const [uploadedImage, setUploadedImage] = useState<string | null>(null)
  const [sourceJobId, setSourceJobId] = useState<string | null>(null)
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [selectedJobId, setSelectedJobId] = useState('')
  const [result, setResult] = useState<Result>({ status: 'idle', workflow: 'generate', title: 'Ready', score: 0, bits: '--', runtime: '--', notes: 'Choose a method, submethod, and workflow, then run the repository-backed action.', imageUrl: null })
  const runTokenRef = useRef(0)

  const selectedMethod = useMemo(() => methods.find((method) => method.id === methodId) ?? methods[0], [methodId])
  const selectedSubmethod = useMemo(() => selectedMethod.submethods.find((submethod) => submethod.id === submethodId) ?? selectedMethod.submethods[0], [selectedMethod, submethodId])
  const selectedWorkflow = useMemo(() => selectedSubmethod.workflows.find((workflow) => workflow.id === workflowId) ?? selectedSubmethod.workflows[0], [selectedSubmethod, workflowId])
  const isGeneration = selectedWorkflow.id === 'generate'
  const needsImage = !isGeneration
  const isSfwAnalysis = selectedMethod.id === 'sfwmark' && !isGeneration
  const messageFieldLabel = selectedMethod.id === 'sfwmark'
    ? 'Watermark variant'
    : selectedMethod.id === 'gaussian-shannon'
      ? 'Message (256 binary bits; "256-bit zero message" means all zeros)'
      : 'Message (48 binary bits)'

  const loadJobs = useCallback(async () => {
    try {
      const query = new URLSearchParams({ method: selectedMethod.id, submethod: selectedSubmethod.id })
      const response = await fetch(`${apiBase}/jobs?${query.toString()}`)
      if (!response.ok) return
      const payload = await response.json()
      setJobs(payload.jobs ?? [])
    } catch {
      setJobs([])
    }
  }, [selectedMethod.id, selectedSubmethod.id])

  useEffect(() => {
    const nextSubmethod = selectedMethod.submethods[0]
    setSubmethodId(nextSubmethod.id)
    setMessage(nextSubmethod.defaultMessage)
    setWorkflowId(nextSubmethod.workflows[0].id)
  }, [methodId, selectedMethod])

  useEffect(() => {
    if (!isGeneration) void loadJobs()
  }, [isGeneration, loadJobs])

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
    setMethodId(id)
    setSubmethodId(nextMethod.submethods[0].id)
    setMessage(nextMethod.submethods[0].defaultMessage)
    setWorkflowId(nextMethod.submethods[0].workflows[0].id)
    clearAnalysisContext()
    resetResult(nextMethod.submethods[0].workflows[0].id)
  }

  function clearAnalysisContext() {
    runTokenRef.current += 1
    setUploadedImage(null)
    setUploadName('No image selected')
    setSourceJobId(null)
    setSelectedJobId('')
  }

  function selectWorkflow(id: WorkflowId) {
    const next = selectedSubmethod.workflows.find((workflow) => workflow.id === id)
    if (!next?.available) return
    setWorkflowId(id)
    resetResult(id)
  }

  function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploadName(file.name)
    const reader = new FileReader()
    reader.onload = () => setUploadedImage(String(reader.result))
    reader.readAsDataURL(file)
    setSourceJobId(null)
  }

  async function runBackendJob(workflow: WorkflowId = selectedWorkflow.id) {
    const runToken = ++runTokenRef.current
    const requestMethodId = methodId
    const workflowSpec = selectedSubmethod.workflows.find((item) => item.id === workflow) ?? selectedWorkflow
    setResult((current) => ({ ...current, workflow, status: 'running', title: `Running ${workflowSpec.label.toLowerCase()}`, notes: `Calling backend at ${apiBase}.` }))

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
          seed,
          imageName: uploadName === 'No image selected' ? null : uploadName,
          imageDataUrl: uploadedImage,
          sourceJobId,
        }),
      })

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}))
        setResult({ status: 'done', workflow, title: 'Backend request failed', score: 0, bits: '--', runtime: '--', notes: errorPayload.error ?? `Backend returned ${response.status}`, imageUrl: null, isError: true })
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
        raw: backendResult.raw,
        imageUrl: backendImageUrl,
        isError: backendResult.status === 'failed' || backendResult.status === 'setup_required' || backendResult.status === 'unsupported',
        jobId: backendJobId,
        jobNumber: backendResult.raw?.job_number ?? null,
      })
      if (backendImageUrl) {
        setUploadedImage(backendImageUrl)
        setUploadName('Generated watermarked image')
        setSourceJobId(backendJobId)
        setSelectedJobId(backendJobId ?? '')
      }
    } catch (error) {
      setResult({ status: 'done', workflow, title: 'Backend not reachable', score: 0, bits: '--', runtime: '--', notes: `${error instanceof Error ? error.message : 'Network error'}. Make sure backend is running on ${apiBase}.`, imageUrl: null, isError: true })
    }
  }

  function detectGeneratedImage() {
    if (!uploadedImage || !sourceJobId) return
    setWorkflowId('verify')
    void runBackendJob('verify')
  }

  function selectPreviousJob(jobId: string) {
    setSelectedJobId(jobId)
    const job = jobs.find((item) => item.job_id === jobId)
    if (!job) return
    setUploadedImage(`${fileBase}${job.image_url}`)
    setSourceJobId(job.job_id)
    setUploadName(`Previous ${job.label}`)
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
    if (workflow === 'verify' && selectedMethod.id === 'sfwmark' && raw) return `Verification distance against the ground-truth pattern: ${typeof raw.verification_distance === 'number' ? raw.verification_distance.toFixed(4) : 'recorded'}. The original repo uses this distance for ROC evaluation.`
    if (workflow === 'identify' && raw) return `Closest candidate is pattern ${raw.predicted_index}; identification was ${raw.identified ? 'correct' : 'incorrect'}. The ground-truth key is used only to score the result.`
    if (workflow === 'verify') return `Verification is represented by the repository's extraction step. Recovered bits are compared with the supplied message and reported as bit error rate or bit accuracy.`
    return backendResult.recovered_payload || 'Extraction completed.'
  }

  function resetRun() {
    resetResult(selectedWorkflow.id)
    setSelectedJobId('')
  }

  function resetResult(nextWorkflow: WorkflowId) {
    setResult({ status: 'idle', workflow: nextWorkflow, title: 'Ready', score: 0, bits: '--', runtime: '--', notes: 'Choose a method, submethod, and workflow, then run the repository-backed action.', imageUrl: null, jobId: null, jobNumber: null, raw: undefined })
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Watermark lab navigation">
        <div className="brand">
          <div className="brand-mark"><Waves size={21} /></div>
          <div><p className="eyebrow">Latent Domain</p><h1>Watermark Lab</h1><span className="owner-name">Chern Ze Hou</span></div>
        </div>
        <div className="sidebar-context"><strong>{selectedMethod.name}</strong><span>{selectedSubmethod.name} · {selectedWorkflow.label}</span></div>
        <div className="deployment"><Cloud size={18} /><div><strong>Repository map</strong><span>3 methods connected</span></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="eyebrow">Repository workflow dashboard</p><h2>Explore latent-domain watermarking methods and their actual evaluation paths</h2></div>
          <div className="run-controls"><button className="icon-button" onClick={resetRun} type="button" aria-label="Reset run" title="Reset run"><RotateCcw size={18} /></button><button className="primary-button" onClick={() => runBackendJob()} type="button"><Play size={18} />Run</button></div>
        </header>

        <section className="method-grid" aria-label="Watermark repositories">
          {methods.map((method) => <button className={`method-card ${method.id === selectedMethod.id ? 'selected' : ''}`} key={method.id} onClick={() => selectMethod(method.id)} style={{ '--method-color': method.color } as CSSProperties} type="button"><span className="method-token">{method.shortName}</span><span><strong>{method.name}</strong><small>{method.category}</small></span></button>)}
        </section>

        <section className="method-navigation" aria-label={`${selectedMethod.name} submethods and workflows`}>
          <div className="navigation-group"><div className="navigation-label"><span>Submethod</span><strong>{selectedMethod.name}</strong></div><div className="submethod-tabs">{selectedMethod.submethods.map((submethod) => <button className={submethod.id === selectedSubmethod.id ? 'active' : ''} key={submethod.id} onClick={() => selectSubmethod(submethod.id)} type="button">{submethod.name}</button>)}</div></div>
          <div className="navigation-group"><div className="navigation-label"><span>Repository action</span><strong>{selectedWorkflow.label}</strong></div><div><div className="workflow-tabs">{selectedSubmethod.workflows.map((workflow) => <button aria-disabled={!workflow.available} className={`${workflow.id === selectedWorkflow.id ? 'active' : ''} ${workflow.available ? '' : 'disabled'}`} disabled={!workflow.available} key={workflow.id} onClick={() => selectWorkflow(workflow.id)} title={workflow.available ? workflow.label : workflow.unavailableReason ?? `${workflow.label} is not implemented by this repository`} type="button">{workflow.id === 'generate' ? <Sparkles size={15} /> : workflow.id === 'identify' ? <Search size={15} /> : <ShieldCheck size={15} />}{workflow.label}</button>)}</div>{selectedSubmethod.workflows.filter((workflow) => !workflow.available).map((workflow) => <p className="workflow-unavailable" key={workflow.id}><strong>{workflow.label} unavailable:</strong> {workflow.unavailableReason}</p>)}</div></div>
        </section>

        <section className="main-grid">
          <div className="control-panel">
            <div className="section-heading"><SlidersHorizontal size={18} /><div><h3>{selectedWorkflow.label}</h3><p className="heading-description">{selectedWorkflow.description}</p></div></div>

            {isGeneration ? <label className="field"><span>Prompt</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} /></label> : null}
            {needsImage ? <>
              <label className="upload-zone primary-upload"><input accept="image/*" onChange={handleUpload} type="file" /><ImageUp size={20} /><span>{uploadName}</span></label>
              <div className={`source-job-note ${sourceJobId ? 'linked' : ''}`}><strong>{sourceJobId ? `Linked generation job: ${sourceJobId}` : 'No generation job linked'}</strong><span>{isSfwAnalysis ? 'SFWMark analysis uses the saved pattern bank and key associated with a generated job.' : 'Upload a generated or edited image for repository extraction/evaluation.'}</span></div>
              <label className="field previous-job-field"><span>Choose previous generated job</span><select value={selectedJobId} onChange={(event) => selectPreviousJob(event.target.value)}><option value="">Select a saved {selectedSubmethod.name} job</option>{jobs.map((job) => <option key={job.job_id} value={job.job_id}>{job.label} · {job.prompt || job.job_id}</option>)}</select></label>
              {sourceJobId && uploadedImage ? <div className="previous-job-preview"><img src={uploadedImage} alt="Selected watermarked output" /><div><strong>{jobs.find((job) => job.job_id === sourceJobId)?.label ?? `Job ${sourceJobId}`}</strong><span>{jobs.find((job) => job.job_id === sourceJobId)?.prompt ?? 'Selected watermarked image'}</span></div></div> : null}
            </> : null}

            <div className="field-row">
              <label className="field"><span>{messageFieldLabel}</span>{selectedMethod.id === 'sfwmark' ? <select value={selectedSubmethod.id} onChange={(event) => selectSubmethod(event.target.value)} disabled={!isGeneration}>{selectedMethod.submethods.map((submethod) => <option key={submethod.id} value={submethod.id}>{submethod.name}</option>)}</select> : <input value={message} onChange={(event) => setMessage(event.target.value)} />}</label>
              <label className="field small-field"><span>Seed</span><input value={seed} onChange={(event) => setSeed(Number(event.target.value))} type="number" disabled={!isGeneration} /></label>
            </div>

            <section className="method-explainer" aria-label={`${selectedMethod.name} explanation`}><div><span>Selected implementation</span><strong>{selectedSubmethod.name}</strong><p>{selectedSubmethod.description}</p></div><div className="latent-facts"><span>Payload and backend behavior</span><strong>{selectedSubmethod.payload}</strong><p>{selectedMethod.mechanism}</p></div><div className="workflow-contract" aria-label={`${selectedWorkflow.label} inputs and outputs`}><div><span>Needs</span><ul>{selectedWorkflow.inputs.map((item) => <li key={item}>{item}</li>)}</ul></div><div><span>Returns</span><ul>{selectedWorkflow.outputs.map((item) => <li key={item}>{item}</li>)}</ul></div><div><span>Repository context</span><p>{selectedWorkflow.source}</p></div></div>{selectedMethod.id === 'sfwmark' ? <div className="workflow-chain" aria-label="SFWMark latent workflow">{['Prompt', 'Gaussian latent noise, 1 x 4 x 64 x 64', 'Fourier watermark insertion', 'Stable Diffusion generation', 'Watermarked image', 'DDIM inversion', 'Extraction / identification'].map((step, index, steps) => <div className="workflow-item" key={step}><span className="workflow-step">{step}</span>{index < steps.length - 1 ? <ArrowRight className="workflow-arrow" aria-hidden="true" size={16} /> : null}</div>)}</div> : null}</section>

            <div className="repo-defaults" aria-label="Repository defaults">{selectedSubmethod.repoDefaults.map((item) => <span key={item}>{item}</span>)}</div>
          </div>

          <div className="preview-panel"><div className="section-heading"><Aperture size={18} /><div><h3>{isGeneration ? 'Generated Image' : 'Analysis Image'}</h3><p className="heading-description">{isGeneration ? 'Only the watermarked output is shown.' : 'The image supplied to this repository workflow.'}</p></div></div><div className="image-stage" style={{ background: uploadedImage ? '#111827' : seedPreview }}>{uploadedImage ? <img src={uploadedImage} alt="Generated or uploaded watermarked preview" /> : <div className="latent-grid" />}<span className="stage-badge">{isGeneration ? 'watermarked image' : 'analysis input'}</span></div><div className="method-detail"><strong>{selectedWorkflow.label}: {selectedSubmethod.name}</strong><p>{selectedWorkflow.description}</p></div></div>

          <div className="result-panel"><div className="section-heading"><Activity size={18} /><div><h3>Results</h3><p className="heading-description">Repository output for the selected action.</p></div></div><div className={`status-strip ${result.status} ${result.isError ? 'error' : ''}`}>{result.status === 'done' ? <CheckCircle2 size={18} /> : <Gauge size={18} />}<span>{result.title}</span></div>
            <div className="metric-grid">{result.workflow === 'generate' ? <><div className="metric"><span>Generation job</span><strong>{result.jobNumber ? `Job #${result.jobNumber}` : result.jobId ? `Job ${result.jobId}` : '--'}</strong></div><div className="metric"><span>Submethod</span><strong>{selectedSubmethod.name}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Output</span><strong>{result.imageUrl ? 'Watermarked image' : '--'}</strong></div></> : result.workflow === 'verify' && selectedMethod.id === 'sfwmark' ? <><div className="metric"><span>GT pattern distance</span><strong>{typeof result.raw?.verification_distance === 'number' ? result.raw.verification_distance.toFixed(4) : '--'}</strong></div><div className="metric"><span>Expected key</span><strong>{result.raw?.key_index ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Repo metric</span><strong>ROC distance</strong></div></> : result.workflow === 'identify' ? <><div className="metric"><span>Identification</span><strong>{result.raw?.identified === undefined ? '--' : result.raw.identified ? 'Correct' : 'Incorrect'}</strong></div><div className="metric"><span>Predicted key</span><strong>{result.raw?.predicted_index ?? '--'}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Candidate bank</span><strong>2048 patterns</strong></div></> : <><div className="metric"><span>Bit error rate</span><strong>{result.bitErrorRate ?? '--'}</strong></div><div className="metric"><span>Recovered output</span><strong>{result.bits}</strong></div><div className="metric"><span>Runtime</span><strong>{result.runtime}</strong></div><div className="metric"><span>Payload</span><strong>{selectedSubmethod.payload}</strong></div></>}</div>
            <div className="api-note"><KeyRound size={18} /><p>{result.notes}</p></div>
            {isGeneration && uploadedImage && sourceJobId && !result.isError ? <div className="result-actions"><button className="secondary-button" onClick={detectGeneratedImage} type="button"><ShieldCheck size={18} />Verify this image</button>{result.imageUrl ? <a className="download-link" href={result.imageUrl} download><Download size={18} />Download watermarked image</a> : null}</div> : null}
          </div>
        </section>
      </section>
    </main>
  )
}

export default App
