// API-contract and responsive-layout checks; all inference responses are mocked.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const assert = require('node:assert/strict');
const catalog = require('../../backend/config/repository_methods.json');

const groups = [
  ['Latent / Initial Noise', [['SFWMark', 'sfwmark'], ['Gaussian Shannon', 'gaussian-shannon'], ['Gaussian Shading', 'gaussian-shading'], ['PRC-Watermark', 'prc-watermark'], ['Tree-Ring', 'tree-ring'], ['Ring-ID', 'ring-id'], ['WIND', 'wind'], ['T2SMark', 't2smark']]],
  ['VAE / Decoder', [['LaWa', 'lawa']]],
  ['Dual Domain / Semantic', [['GaussMarker', 'gaussmarker'], ['SEAL', 'seal']]],
  ['Optimization / Tamper Aware', [['ROBIN', 'robin'], ['TAG-WM', 'tag-wm']]],
  ['Learned Detector', [['SERUM', 'serum']]],
];
const labels = { verify: 'Verification', identify: 'Identification', detect: 'Detection', decode: 'Decoding', localize: 'Tamper localization' };
const originalVariants = {
  sfwmark: [['hsqr', 'HSQR'], ['hstr', 'HSTR']],
  'gaussian-shannon': [['gaussian', 'Gaussian coding'], ['ldpc', 'LDPC coding']],
  lawa: [['lawa-48', 'LaWa 48-bit']],
  'gaussian-shading': [['chacha', 'ChaCha20'], ['simple', 'Simple XOR']],
  'prc-watermark': [['prc', 'PRC']],
};
const variantGraphText = {
  'sfwmark/hsqr': 'QR sign pattern, channel 3',
  'sfwmark/hstr': 'Hermitian rings + heterogeneous channel',
  'gaussian-shannon/gaussian': 'Majority vote across copies',
  'gaussian-shannon/ldpc': 'LDPC BP; vote-and-retry fallback',
  'gaussian-shading/chacha': 'ChaCha20 encryption',
  'gaussian-shading/simple': 'XOR with random binary key',
  'tree-ring/ring': 'Concentric Fourier rings',
  'tree-ring/rand': 'Random Fourier coefficients',
  'tree-ring/zeros': 'Zero Fourier coefficients',
  'wind/full': 'Global fallback when needed',
  'wind/fast': 'Image + one-entry registry',
  'tag-wm/trainable': 'Trained DVRD refinement',
  'tag-wm/trainfree': 'Train-free adaptive refinement',
  'serum/serum': 'Train score model only',
};

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_EXECUTABLE ? { executablePath: process.env.CHROME_EXECUTABLE } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], requests = [];
    let setupFailure = false;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/jobs?**', route => route.fulfill({ json: { jobs: [] } }));
    await page.route('**/files/ui-*.png', route => route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') }));
    await page.route('**/watermark/generate', route => {
      requests.push(route.request().postDataJSON());
      return route.fulfill({ json: { result: { job_id: '123456abcdef', status: setupFailure ? 'setup_required' : 'completed', workflow: 'generate', detection_score: 0, recovered_payload: setupFailure ? 'NVIDIA CUDA setup required' : 'Saved', runtime: 'real', image_url: setupFailure ? null : '/files/ui-image.png', raw: { job_number: 1 } } } });
    });
    await page.route('**/detect', route => {
      const request = route.request().postDataJSON();
      requests.push(request);
      return route.fulfill({ json: { result: { job_id: 'abcdef123456', status: 'completed', workflow: 'detect', detection_score: 0, recovered_payload: '0101', runtime: 'real', image_url: null, raw: { summary: 'Native statistic; calibration required.', metrics: [{ label: 'Native score', value: .125 }, { label: 'Candidate count', value: 16 }], ...(request.method === 'tag-wm' ? { mask_url: '/files/ui-mask.png' } : {}) } } } });
    });
    await page.goto(process.env.UI_URL || 'http://127.0.0.1:5173');
    const selectCategory = async name => page.locator('.category-button').filter({ has: page.locator('strong').getByText(name, { exact: true }) }).click();
    const selectMethod = async name => page.locator('.method-card').filter({ has: page.locator('strong').getByText(name, { exact: true }) }).click();
    for (const [category, methods] of groups) {
      await selectCategory(category);
      for (const [name, id] of methods) {
        await selectMethod(name);
        assert.equal(await page.locator('.planned-state').count(), 0);
        assert.equal(await page.getByRole('button', { name: 'Run Generation', exact: true }).isEnabled(), true);
        const variants = catalog[id]?.variants.map(variant => [variant, `${name} / ${variant}`]) || originalVariants[id];
        for (const [variant, variantLabel] of variants) {
          await page.locator('.submethod-tabs').getByRole('button', { name: variantLabel, exact: true }).click();
          const panel = page.locator('.implementation-panel');
          const graph = await panel.locator('.process-map').textContent();
          if (variantGraphText[`${id}/${variant}`]) assert.ok(graph.includes(variantGraphText[`${id}/${variant}`]), `${id}/${variant} graph is not specific to its implementation`);
          assert.equal(await panel.getByRole('link', { name: 'Reviewed repository source' }).count(), 1);
          assert.ok((await panel.locator('.upstream-reference').textContent()).length > 80);
          assert.equal(await panel.getByLabel('Website defaults').count(), 1);
          assert.ok(!(await panel.locator('.repo-defaults').textContent()).includes('Awaiting GPU validation'));
          if (catalog[id]) {
            const source = await panel.getByRole('link').getAttribute('href');
            assert.ok(source.startsWith(`${catalog[id].repo_url}/blob/${catalog[id].revision}/`));
            const defaults = await panel.locator('.repo-defaults').textContent();
            for (const option of Object.values(catalog[id].options)) assert.ok(defaults.includes(`${option.label}: ${option.default}`), `${id} default drift: ${option.label}`);
            for (const row of await panel.locator('.process-row').all()) {
              const label = await row.locator('.process-label strong').textContent();
              const offline = label.includes('training') || label === 'Optimization';
              assert.equal(await row.locator('.process-label span').textContent(), offline ? 'Offline upstream' : 'Website');
              if (offline) assert.equal(await page.locator('.workflow-tabs').getByRole('button', { name: label, exact: true }).isDisabled(), true);
            }
          }
          if (id === 'sfwmark') {
            assert.equal(await page.getByLabel('Seed (fixed upstream)').isDisabled(), true);
            assert.equal(await page.getByLabel('Seed (fixed upstream)').inputValue(), '42');
          }
          if (id === 'gaussian-shannon') {
            await page.locator('.workflow-tabs').getByRole('button', { name: 'Verification', exact: true }).click();
            await page.locator('input[type=file]').setInputFiles({ name: 'test.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') });
            await page.getByAltText('Generated or uploaded watermarked preview').waitFor();
            assert.equal(await page.getByRole('button', { name: 'Run Verification', exact: true }).isEnabled(), variant !== 'ldpc');
            await page.locator('.workflow-tabs').getByRole('button', { name: 'Generation', exact: true }).click();
          }
          await page.getByRole('button', { name: 'Run Generation', exact: true }).click();
          await page.locator('.status-strip.done').waitFor();
          assert.equal(requests.at(-1).method, id);
          assert.equal(requests.at(-1).analysisMode, 'generate');
          assert.equal(requests.at(-1).submethodId, variant);
          if (id === 'sfwmark') assert.equal(requests.at(-1).seed, 42);
          const actions = catalog[id]?.adapter_workflows.filter(action => action !== 'generate') || (id === 'prc-watermark' ? ['detect', 'decode'] : id === 'sfwmark' ? ['verify', 'identify'] : ['verify']);
          for (const action of actions) {
            const actionLabel = id === 'prc-watermark' ? action === 'detect' ? 'Detect' : 'Decode' : labels[action];
            await page.locator('.workflow-tabs').getByRole('button', { name: actionLabel, exact: true }).click();
            const contract = panel.locator('.workflow-contract');
            assert.ok((await contract.textContent()).length > 100);
            if (id === 'prc-watermark') {
              const needs = await contract.locator('div').first().textContent();
              assert.ok(!needs.includes('Posterior vector') && !needs.includes('Maximum BP iterations'));
            }
            if (id === 'tag-wm') assert.ok((await contract.textContent()).includes('Both actions return the same full analysis'));
            await page.locator('.control-panel').getByRole('button', { name: `Run ${actionLabel}`, exact: true }).click();
            await page.locator('.status-strip.done').waitFor();
            assert.equal(requests.at(-1).analysisMode, action);
            assert.equal(requests.at(-1).sourceJobId, '123456abcdef');
            if (catalog[id]) assert.ok((await page.locator('.metric-grid').textContent()).includes('0.125'));
            if (id === 'tag-wm') assert.equal(await page.getByAltText('Predicted tamper localization mask').count(), 1);
          }
          await page.locator('.workflow-tabs').getByRole('button', { name: 'Generation', exact: true }).click();
        }
      }
    }
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const [category, methods] of groups) {
        await selectCategory(category);
        for (const [name] of methods) {
          await selectMethod(name);
          const overflow = await page.evaluate(() => ({ width: document.documentElement.clientWidth, content: document.documentElement.scrollWidth,
            clipped: [...document.querySelectorAll('.category-copy, .method-copy, .workflow-step, .repo-defaults span, .upstream-reference, .workflow-contract > div')].filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent) }));
          assert.ok(overflow.content <= overflow.width, `${name} overflows at ${width}: ${JSON.stringify(overflow)}`);
          assert.deepEqual(overflow.clipped, [], `${name} clipped labels at ${width}`);
        }
      }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await selectCategory('Latent / Initial Noise');
    await selectMethod('Ring-ID');
    await page.screenshot({ path: '/tmp/ldwm-repositories-desktop.png', fullPage: true });
    setupFailure = true;
    await page.getByRole('button', { name: 'Run Generation', exact: true }).click();
    await page.locator('.status-strip.done').waitFor();
    assert.ok((await page.locator('.result-panel').textContent()).includes('NVIDIA CUDA setup required'));
    await page.setViewportSize({ width: 390, height: 844 });
    await selectCategory('Optimization / Tamper Aware');
    await selectMethod('TAG-WM');
    await page.screenshot({ path: '/tmp/ldwm-repositories-mobile.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log(`PASS: 14 methods / 21 variants, every action, source links, catalog defaults, variant graphs, offline labels, LDPC state requirement, fixed SFW seed, metrics, mask, setup error, and 320-1440px layouts. ${requests.length} mocked requests.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
