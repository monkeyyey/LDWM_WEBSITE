import catalog from '../../backend/config/repository_methods.json'
import type { RepositoryMethodId, WorkflowId } from './methodCatalog'

export type ProcessSpec = { workflow: WorkflowId; label: string; steps: string[] }
export type WorkflowSpec = {
  id: WorkflowId
  label: string
  description: string
  backendWorkflow: 'generate' | 'detect' | null
  available: boolean
  inputs: string[]
  outputs: string[]
  source: string
  unavailableReason?: string
}
export type SubmethodSpec = {
  id: string
  name: string
  description: string
  payload: string
  defaultMessage: string
  messageMode?: 'editable' | 'generated' | 'variant'
  repoDefaults: string[]
  upstreamDefaults?: string
  sourceUrl?: string
  backendBehavior?: string
  processes?: ProcessSpec[]
  workflows: WorkflowSpec[]
}

type Flow = Pick<WorkflowSpec, 'id' | 'label' | 'description' | 'inputs' | 'outputs' | 'source'> & { steps: string[] }
type Detail = {
  description: string
  payload: string
  behavior: string
  fixedDefaults: string[]
  upstreamDefaults: string
  sourceFile: string
  flows: Flow[]
}

const linked = 'Compatible generation job (saved model, settings and watermark state)'
const generated = ['Watermarked image', 'Linked job with private analysis state']
const noThreshold = 'A distance is not a presence decision; a negative-image calibration set is required for a threshold.'

function details(id: RepositoryMethodId, variant: string): Detail {
  switch (id) {
    case 'tree-ring': {
      const pattern = variant === 'ring' ? 'Concentric Fourier rings' : variant === 'rand' ? 'Random Fourier coefficients' : 'Zero Fourier coefficients'
      return {
        description: `${pattern} replace coefficients inside the selected circular frequency mask.`,
        payload: `${variant} Fourier pattern; no message bits`,
        behavior: 'Saves the actual pattern and mask. Detection compares inverted noise with that saved pattern, not a candidate bank.',
        fixedDefaults: ['Image: 512 x 512', 'Mask: circle', 'Injection: complex', 'Measurement: complex L1'],
        upstreamDefaults: 'run_tree_ring_watermark.py defaults to rand, channel 0, radius 10, watermark seed 999999, 50 generation steps and guidance 7.5. Inversion defaults to the generation step count. This website starts with ring, channel 3 and an explicit 50 inversion steps.',
        sourceFile: 'run_tree_ring_watermark.py',
        flows: [
          { id: 'generate', label: 'Generation', description: `Insert ${variant} coefficients into initial noise, then generate an image.`, inputs: ['Prompt', 'Seed and Fourier settings', 'Diffusion model'], outputs: generated, source: 'Calls get_watermarking_pattern, get_watermarking_mask and inject_watermark. Other upstream masks and injection modes are not exposed.', steps: ['Gaussian noise', pattern, 'Replace masked Fourier coefficients', 'Inverse FFT to real noise', 'Diffusion generation', 'Image + saved pattern'] },
          { id: 'detect', label: 'Detection', description: 'Measure complex Fourier L1 distance to the saved pattern.', inputs: ['Image', linked], outputs: ['Fourier L1 distance (lower is closer)'], source: noThreshold, steps: ['Image + saved pattern', 'VAE encoding', 'Empty-prompt diffusion inversion', 'FFT + saved mask', 'Complex L1 distance'] },
        ],
      }
    }
    case 'ring-id': return {
      description: 'Binary-valued rings in channel 3 and a heterogeneous pattern in channel 0 distinguish candidates in a saved bank.',
      payload: 'Pattern-bank index; not an account ID',
      behavior: 'Verification tests the expected candidate. Identification searches the saved bank and compares the nearest index with the job label.',
      fixedDefaults: ['Image: 512 x 512', 'Radii: 3 to 14', 'Channels: 0 + 3', 'Ring levels: 2'],
      upstreamDefaults: 'verify.py and identify.py use assigned_keys=-1 for all 2048 combinations, ring range 64, fix_gt=1, time_shift=1 and channel_min=1. The website uses 2048 for that full bank and selects index 628 by default. Smaller banks are sampled per job.',
      sourceFile: 'identify.py',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Create the candidate bank, select its configured index and watermark initial noise.', inputs: ['Prompt and seed', 'Candidate-bank settings and valid pattern index', 'Diffusion model'], outputs: [...generated, 'Saved bank, mask and expected index'], source: 'Native RingID pattern construction, optional real-projection correction and spatial time shift. No persistent account-to-key registry is created.', steps: ['Build heterogeneous + ring bank', 'Optional correction + time shift', 'Select pattern index', 'Fourier insertion into noise', 'Diffusion generation', 'Image + bank + index'] },
        { id: 'verify', label: 'Verification', description: 'Compare the recovered pattern only with the expected saved candidate.', inputs: ['Image', linked], outputs: ['Expected pattern index', 'Fourier L1 distance'], source: noThreshold, steps: ['Image + expected candidate', 'Empty-prompt inversion', 'FFT + saved mask', 'Expected-pattern L1 distance'] },
        { id: 'identify', label: 'Identification', description: 'Compare all saved candidates and return the closest index.', inputs: ['Image', linked], outputs: ['Predicted and expected indices', 'Closest distance and candidate count', 'Correct/incorrect against the job label'], source: 'A nearest candidate is returned even for unrelated images; correctness against a known label is not a calibrated presence test.', steps: ['Image + saved candidate bank', 'Empty-prompt inversion', 'Fourier distance to each candidate', 'Minimum-distance index', 'Compare with expected index'] },
      ],
    }
    case 'wind': {
      const full = variant === 'full'
      return {
        description: full ? 'Precomputes a bank of M grouped noises and retains the native global-search fallback.' : 'Generates noise on demand and searches only registered entries. This website registers one noise per generation job.',
        payload: 'Group index + noise index',
        behavior: full ? 'Restores the full job registry. Group retrieval and rotation-aware matching precede an optional sliding-window cosine search across the registry.' : 'Restores this job\'s single registered noise. M defines the possible noise-index space, not a registry of M saved candidates. No global fallback runs.',
        fixedDefaults: ['Image: 512 x 512', 'Guidance: 7.5', 'Group channels: 0 + 3'],
        upstreamDefaults: 'Both WIND scripts default to M=10000, assigned_keys=-1 (all 2048 groups), 50 generation steps and guidance 7.5. The website uses 2048 and 50 explicit inversion steps. Benchmark trials and a registry shared across jobs are not exposed.',
        sourceFile: full ? 'WIND_full.py' : 'WIND_fast.py',
        flows: [
          { id: 'generate', label: 'Generation', description: full ? 'Precompute grouped noises, select a noise identity and generate.' : 'Select a noise identity, derive its noise, insert the group mark and register it.', inputs: ['Prompt and seed', 'Group-bank settings and noise-index count M', 'Diffusion model'], outputs: [...generated, full ? 'Saved full noise registry and expected identity' : 'One registered noise and its expected identity'], source: full ? 'Full mode stores the native precomputed watermarked latents. Large M can require substantial memory and disk.' : 'Fast mode keeps the entry created by this job; it does not populate all M possible noises.', steps: full ? ['Build group patterns', 'Precompute M grouped noises', 'Select noise identity', 'Diffusion generation', 'Image + full registry'] : ['Build group patterns', 'Choose noise identity', 'Hash-derived noise + group insertion', 'Diffusion generation', 'Image + one registered noise'] },
          { id: 'identify', label: 'Identification', description: 'Retrieve the group, match the registered noise and compare with the saved identity.', inputs: ['Image', linked], outputs: ['Predicted group and noise index', 'Expected noise and identification correctness', 'First-stage L2, registry count and fallback flag'], source: 'The returned L2 is the first-stage distance, not a calibrated probability. ' + (full ? 'Native rotation search and sliding-window fallback are preserved.' : 'Search is restricted to the job registry; no global fallback.'), steps: full ? ['Image + full registry', 'Diffusion inversion', 'Fourier group retrieval', 'Rotation-aware group search', 'Global fallback when needed', 'Predicted identity + correctness'] : ['Image + one-entry registry', 'Diffusion inversion', 'Fourier group retrieval', 'Rotation-aware registered-noise search', 'Predicted identity + correctness'] },
        ],
      }
    }
    case 't2smark': return {
      description: 'The SD 2.1 path embeds a session key under a master key in one channel and a random message under that session key in the other three.',
      payload: 'Random session key + random message (16 + 256 bits by default)',
      behavior: 'Generates fresh master/session keys per job. Both analysis actions recover the session key and evaluate message recovery; only Decode exposes the recovered bit string.',
      fixedDefaults: ['Image: 512 x 512', 'Message channels: remaining 3'],
      upstreamDefaults: 'option.py defaults to SD 2.1 (not base), key_length=16, msg_length=256, key_channel_idx=0, tau=0.674, 50 generation and 10 inversion steps, guidance 7.5. The upstream SD 3.5 path and fixed-key experiments are not integrated.',
      sourceFile: 'option.py',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Tail-sample key and message channels, then run SD 2.1 generation.', inputs: ['Prompt and seed', 'Key length, message length, channel and tail threshold', 'Compatible SD 2.1 model'], outputs: [...generated, 'Saved master key, session key and random message'], source: 'Uses the native T2SMark encoders; the message field is not user-editable.', steps: ['Random master + session key + message', 'Encode session key under master key', 'Encode message under session key', 'Combine four noise channels', 'SD 2.1 generation', 'Image + key state'] },
        { id: 'detect', label: 'Detection', description: 'Recover the key-channel L1 statistic and evaluate two-stage bit recovery.', inputs: ['Image', linked], outputs: ['Key L1 statistic', 'Session-key accuracy', 'Message accuracy, BER and bit count'], source: 'No calibrated binary presence decision. Message decoding uses the recovered session key, not the saved ground truth.', steps: ['Image + saved master key', 'VAE encoding + naive inversion', 'Recover session key + L1 statistic', 'Decode message with recovered key', 'Key/message accuracy'] },
        { id: 'decode', label: 'Decoding', description: 'Run the same two-stage recovery and return the recovered message bits.', inputs: ['Image', linked], outputs: ['Recovered message bits', 'Key L1 statistic and session-key accuracy', 'Message accuracy, BER and bit count'], source: 'Saved session/message bits are used only for evaluation. No candidate-bank identification.', steps: ['Image + saved master key', 'VAE encoding + naive inversion', 'Recover session key', 'Decode message with recovered key', 'Bits + accuracy + BER'] },
      ],
    }
    case 'gaussmarker': return {
      description: 'Combines a ChaCha20 spatial bit watermark with a Fourier ring pattern; a trained Gaussian Noise Restorer improves bit recovery.',
      payload: 'Artifact-defined 256-bit watermark + Fourier pattern',
      behavior: 'Loads a matching W1 watermark artifact and GNR checkpoint. Restored spatial accuracy and the original inverted-noise Fourier distance feed the released ensemble classifier.',
      fixedDefaults: ['Image: 512 x 512', 'Copy factors: 1 x 8 x 8', 'Fourier channel: 3', 'FPR: 1e-6', 'Users: 1,000,000'],
      upstreamDefaults: 'gaussmarker_gen.py uses a ring on channel 3, radius 4, seed 999999 and 50 steps. gaussmarker_det.py defaults to restorer width 128, input type 0 and FPR 0.01; this adapter constructs its watermark evaluator with FPR 1e-6. No FPR-derived ensemble decision is returned.',
      sourceFile: 'gaussmarker_det.py',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Sample spatial watermark noise, insert the Fourier pattern and generate.', inputs: ['Prompt and seed', 'Matching W1 artifact and GNR checkpoint', 'Diffusion model and Fourier settings'], outputs: [...generated, 'Saved W1, Fourier pattern/mask and GNR fingerprint'], source: 'The current runner loads the GNR even during generation. The released sd21_cls2.pkl classifier must be present for analysis.', steps: ['W1 artifact + Fourier key', 'ChaCha spatial-noise sampling', 'Fourier ring insertion', 'Diffusion generation', 'Image + saved dual-domain state'] },
        { id: 'detect', label: 'Detection', description: 'Analyze spatial and Fourier signals separately, then combine their scores.', inputs: ['Image', linked, 'Same GNR checkpoint and released ensemble classifier'], outputs: ['Raw and restored bit accuracy', 'Restored BER and Fourier L1 distance', 'Ensemble probability (uncalibrated operating point)'], source: 'Fourier comparison uses the inverted noise, not the GNR output. Affine alignment is not enabled; the classifier score has no app-applied threshold.', steps: ['Image + saved state', 'VAE sampling + diffusion inversion', 'Spatial signs -> GNR -> decrypt/vote', 'Separately: original-noise Fourier L1', 'Released ensemble classifier', 'Accuracy + distance + probability'] },
        { id: 'train', label: 'Restorer training', description: 'Prepare a W1 artifact and train its matching restorer outside the website.', inputs: ['W1 artifact', 'Training data, distortions and GNR configuration'], outputs: ['Matching GNR checkpoint'], source: 'Offline upstream gen_watermark.py and train_GNR.py; no training is launched by a website action.', steps: ['Prepare W1 watermark artifact', 'Generate distorted training pairs', 'Train Gaussian Noise Restorer', 'GNR checkpoint'] },
      ],
    }
    case 'seal': return {
      description: 'Derives patchwise initial noise from image semantics using a caption, a sentence embedding and locality-sensitive hashing.',
      payload: 'Caption-derived patch keys; no user message',
      behavior: 'Generation runs twice. Verification makes a fresh caption of the analyzed image; it does not reuse the preliminary caption as a secret key.',
      fixedDefaults: ['Image: 512 x 512', 'Semantic hash seed: 42'],
      upstreamDefaults: 'SEAL.py defaults to k=1024 patches and b=7 hash bits. The adapter loads Salesforce/blip2-flan-t5-xl and kasraarabi/finetuned-caption-embedding. The upstream threshold/attack sweeps are not a website decision rule.',
      sourceFile: 'SEAL.py',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Generate a preliminary image, derive semantic noise, then generate the final image.', inputs: ['Prompt and seed', 'Diffusion model, BLIP-2 and sentence encoder weights', 'Patch count k and hash bits b'], outputs: [...generated, 'Preliminary caption in job metadata'], source: 'Only the final watermarked image is returned. Semantic model weights must also be available; no watermark training runs here.', steps: ['Prompt -> preliminary image', 'BLIP-2 caption', 'Normalized sentence embedding', 'SimHash -> patchwise Gaussian noise', 'Second diffusion generation', 'Final image'] },
        { id: 'verify', label: 'Verification', description: 'Compare inverted noise with freshly reconstructed semantic noise patch by patch.', inputs: ['Image', linked, 'Same diffusion, caption and embedding models'], outputs: ['Minimum and mean patch L2', 'Patch count', 'Fresh caption and patch distances in backend output'], source: 'The app requires a linked job to restore model/settings, not an original secret caption. No calibrated detection threshold or tamper mask is returned.', steps: ['Image -> fresh caption + embedding', 'Reconstruct semantic patch noise', 'Separately: image diffusion inversion', 'Compare corresponding noise patches', 'Patch L2 statistics'] },
      ],
    }
    case 'robin': return {
      description: 'Loads an optimized Fourier watermark and learned hiding-prompt conditioning for insertion at an intermediate diffusion step.',
      payload: 'Optimized pattern + conditioning tensor',
      behavior: 'Does not optimize on Run. Verification compares the saved pattern at the configured intermediate inversion step, not at final noise.',
      fixedDefaults: ['Image: 512 x 512', 'Hiding guidance: 7.5', 'Measurement: complex L1'],
      upstreamDefaults: 'The upstream injection CLI uses channel 0 and radii 5 to 30. The website defaults to channel 3 and step 35; the supplied opt_wm/opt_acond artifact must match the model, mask and step schedule. These are not interchangeable trained settings.',
      sourceFile: 'inject_wm_inner_latent_robin.py',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Load optimized artifacts and inject the pattern at the saved configuration\'s intermediate step.', inputs: ['Prompt and seed', 'Checkpoint containing opt_wm and opt_acond', 'Matching diffusion model, mask and step schedule'], outputs: [...generated, 'Saved optimized pattern, conditioning and mask'], source: 'Optimization remains offline. Changing mask or steps without matching optimized artifacts does not reproduce the upstream experiment.', steps: ['Prompt + optimized artifacts', 'Denoise to injection step', 'Fourier pattern insertion', 'Learned hiding conditioning', 'Continue generation', 'Watermarked image'] },
        { id: 'verify', label: 'Verification', description: 'Invert to the intermediate state and measure the masked Fourier discrepancy.', inputs: ['Image', linked], outputs: ['Intermediate step index', 'Fourier L1 distance'], source: noThreshold, steps: ['Image + saved pattern', 'VAE encoding', 'Empty-prompt inversion with intermediate states', 'Select injection-step state', 'Masked Fourier L1 distance'] },
        { id: 'optimize', label: 'Optimization', description: 'Optimize the pattern and hiding conditioning outside the website.', inputs: ['Upstream optimization configuration', 'Matching diffusion model and reference data'], outputs: ['opt_wm and opt_acond checkpoint'], source: 'Offline upstream optimization; not a generation or verification button.', steps: ['Reference data + model + mask', 'Optimize watermark and hiding conditioning', 'Save optimized artifact'] },
      ],
    }
    case 'tag-wm': {
      const trained = variant === 'trainable'
      const refinement = trained ? 'Trained DVRD refinement' : 'Train-free adaptive refinement'
      return {
        description: `Jointly samples message and localization-template signals. ${refinement} estimates edited regions after inversion.`,
        payload: 'Random message (256 bits by default) + fixed localization template',
        behavior: 'Decode and Localize both run the full analysis and return bits plus a predicted mask. Tamper-aware voting is optional; there is no candidate-user search.',
        fixedDefaults: ['Image: 512 x 512', 'Shuffle/encryption seeds: 133563', 'Template intervals: 3', 'FPR: 1e-6', 'Users: 1,000,000'],
        upstreamDefaults: 'applied_to_sd2/test.py defaults to 256 bits, 50 generation/10 inversion steps, guidance 7.5, tamper confidence 0.7 and trainable refinement. Its calc_wm_use_tamper_loc defaults to false; the website enables tamper-aware voting. Train-free refinement needs no DVRD weights.',
        sourceFile: 'applied_to_sd2/test.py',
        flows: [
          { id: 'generate', label: 'Generation', description: 'Jointly encode a random message and alternating localization template into noise.', inputs: ['Prompt and seed', 'SD 2.1 model and message/localization settings', ...(trained ? ['DVRD checkpoint (also loaded during generation)'] : [])], outputs: [...generated, 'Saved message and localization template'], source: trained ? 'The runner binds the DVRD checkpoint fingerprint to the job; analysis requires the same checkpoint.' : 'Uses native checkpoint-free refinement. It is not a fallback for missing trainable weights.', steps: ['Random message + fixed template', 'Redundancy + shuffle + ChaCha20', 'Joint truncated-noise sampling', 'Diffusion generation', 'Image + message/template state'] },
          ...(['decode', 'localize'] as const).map((action): Flow => ({ id: action, label: action === 'decode' ? 'Decoding' : 'Tamper localization', description: 'Recover the message and template, refine the tamper map and evaluate the recovered bits.', inputs: ['Image', linked, ...(trained ? ['Same DVRD checkpoint'] : [])], outputs: ['Recovered bits, accuracy and BER', 'Predicted tamper mask', 'Detection/traceability thresholds and decisions'], source: 'Both actions return the same full analysis. The mask is a prediction, not localization accuracy or IoU; those need a ground-truth edit mask.', steps: ['Image + message/template state', 'Diffusion inversion + de-embedding', 'Compare localization template', refinement, 'Vote with optional tamper exclusion', 'Bits + decisions + predicted mask'] })),
        ],
      }
    }
    case 'serum': return {
      description: 'Mixes a saved watermark grid into initial noise and detects its signal using a trained CNN on VAE-encoded image latents.',
      payload: 'Saved noise-grid signal; no decoded bits',
      behavior: 'The released training optimizer updates the score model only, not the watermark grid. Generation uses the loaded grid; detection requires VAE encoding but no diffusion inversion.',
      fixedDefaults: ['Image required: 512 x 512', 'Latent required: 4 x 64 x 64', 'Model and sampling: loaded YAML'],
      upstreamDefaults: 'configs/config_sd21.yaml specifies SD 2.1 base, 50 sampling steps, guidance 7.5 and noise_mix_alpha=0.5. Actual website values come from the supplied YAML, not generic model or inference-step defaults; the complete configuration is saved per job.',
      sourceFile: 'configs/config_sd21.yaml',
      flows: [
        { id: 'generate', label: 'Generation', description: 'Mix the normalized saved grid with random noise and sample using the supplied YAML.', inputs: ['Prompt and seed', 'Matching YAML, watermark grid and detector checkpoints', 'Diffusion model and VAE specified by the YAML'], outputs: [...generated, 'Snapshot of configuration and detector weights'], source: 'The current runner loads the detector during generation and snapshots it for analysis. The generic MODEL_ID environment setting does not select SERUM\'s model.', steps: ['Saved grid + random Gaussian noise', 'Normalize grid + weighted mixture', 'YAML-configured diffusion sampling', 'VAE decode + export', 'Image + config/detector snapshot'] },
        { id: 'detect', label: 'Detection', description: 'VAE-encode the image and run the saved latent CNN detector.', inputs: ['512 x 512 image', linked, 'VAE specified in the saved configuration'], outputs: ['Detector sigmoid score'], source: 'No diffusion inversion, message decoding or candidate identification. A sigmoid score is not a calibrated detection probability or binary decision.', steps: ['512 x 512 image', 'VAE encoding', 'Saved latent CNN detector', 'Sigmoid score (no threshold)'] },
        { id: 'train', label: 'Detector training', description: 'Train the score model on clean and watermarked latents outside the website.', inputs: ['Clean data and augmented watermarked training data', 'Fixed watermark grid and matching model configuration'], outputs: ['Trained detector and saved watermark/configuration'], source: 'src/training/train.py _prepare_optimizer includes score_model.parameters() only. This is not joint grid-and-detector optimization.', steps: ['Fixed grid + clean/watermarked data', 'Augmentation + VAE latent preparation', 'Train score model only', 'Save detector and watermark artifacts'] },
      ],
    }
  }
}

export function repositorySubmethods(id: RepositoryMethodId, name: string): SubmethodSpec[] {
  const spec = catalog[id]
  return spec.variants.map((variant) => {
    const detail = details(id, variant)
    return {
      id: variant, name: `${name} / ${variant}`, description: detail.description,
      payload: detail.payload, defaultMessage: detail.payload, messageMode: 'generated',
      backendBehavior: detail.behavior,
      // Read configurable defaults from the same catalog as the backend and form controls.
      repoDefaults: [...Object.values(spec.options).map((option) => `${option.label}: ${option.default}`), ...detail.fixedDefaults,
        ...(id === 'serum' ? [] : [`Model fallback: ${spec.default_model} (server-overridable)`])],
      upstreamDefaults: detail.upstreamDefaults,
      sourceUrl: `${spec.repo_url}/blob/${spec.revision}/${detail.sourceFile}`,
      processes: detail.flows.map((flow) => ({ workflow: flow.id, label: flow.label, steps: flow.steps })),
      workflows: detail.flows.map(({ steps: _steps, ...flow }) => {
        const available = (spec.adapter_workflows as string[]).includes(flow.id)
        return { ...flow, available, backendWorkflow: available ? flow.id === 'generate' ? 'generate' : 'detect' : null,
          unavailableReason: available ? undefined : 'Offline upstream preparation; not available in the website.' }
      }),
    }
  })
}
