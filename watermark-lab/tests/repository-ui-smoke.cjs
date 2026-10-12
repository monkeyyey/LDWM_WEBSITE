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
        for (const variant of catalog[id]?.variants || [null]) {
          if (variant) await page.locator('.submethod-tabs').getByRole('button', { name: `${name} / ${variant}`, exact: true }).click();
          await page.getByRole('button', { name: 'Run Generation', exact: true }).click();
          await page.locator('.status-strip.done').waitFor();
          assert.equal(requests.at(-1).method, id);
          assert.equal(requests.at(-1).analysisMode, 'generate');
          if (variant) assert.equal(requests.at(-1).submethodId, variant);
          const actions = catalog[id]?.adapter_workflows.filter(action => action !== 'generate') || [id === 'prc-watermark' ? 'detect' : 'verify'];
          for (const action of actions) {
            const actionLabel = catalog[id] ? labels[action] : id === 'prc-watermark' ? 'Detect' : 'Verification';
            await page.locator('.workflow-tabs').getByRole('button', { name: actionLabel, exact: true }).click();
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
            clipped: [...document.querySelectorAll('.category-copy, .method-copy, .workflow-step')].filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent) }));
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
    console.log(`PASS: 14 methods, every new variant/action, linked state, metrics, mask, setup error, and 320-1440px layouts. ${requests.length} mocked requests.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
