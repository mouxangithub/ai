/**
 * Model failover chain editor — full combobox per fallback row.
 */
const FallbackModels = (() => {
  let root = null;
  let rows = [];
  let providers = [];
  let getProvider = () => 'opencode-zen';

  function defaultRow() {
    return { provider: getProvider(), model: '', apiKey: '', baseUrl: '', label: '' };
  }

  function mount(container, opts = {}) {
    root = typeof container === 'string' ? document.querySelector(container) : container;
    if (!root) return;
    getProvider = opts.getProvider || getProvider;
    providers = opts.providers || [];
    root.innerHTML = `
      <div class="fallback-models-head">
        <p class="field-hint" id="fallbackHint">主模型失败时按顺序尝试以下备用模型（仅在尚未输出内容时切换）。</p>
        <button type="button" class="btn small" id="fallbackAddBtn">+ 添加备用模型</button>
      </div>
      <div class="fallback-models-list" id="fallbackList"></div>
    `;
    root.querySelector('#fallbackAddBtn')?.addEventListener('click', () => {
      rows.push({ ...defaultRow(), _combo: null });
      render();
      persistChange();
    });
    setRows(opts.initial || []);
  }

  function providerOptions(selected) {
    const opts = providers.length ? providers : ['opencode-zen', 'openrouter', 'siliconflow', 'bigmodel'];
    return opts.map((p) => {
      const id = typeof p === 'string' ? p : (p.id || p);
      return `<option value="${id}"${id === selected ? ' selected' : ''}>${id}</option>`;
    }).join('');
  }

  function render() {
    const list = root?.querySelector('#fallbackList');
    if (!list) return;
    list.innerHTML = '';
    rows.forEach((row, idx) => {
      const el = document.createElement('div');
      el.className = 'fallback-row';
      el.innerHTML = `
        <div class="fallback-row-head">
          <span class="fallback-row-index">#${idx + 1}</span>
          <button type="button" class="btn small ghost fallback-remove" data-idx="${idx}">删除</button>
        </div>
        <label class="field"><span class="field-label">标签</span>
          <input type="text" class="fallback-label" data-idx="${idx}" placeholder="可选，如：备用 DeepSeek" value="${escapeAttr(row.label || '')}">
        </label>
        <label class="field"><span class="field-label">服务商</span>
          <select class="fallback-provider" data-idx="${idx}">${providerOptions(row.provider)}</select>
        </label>
        <label class="field"><span class="field-label">模型</span>
          <div class="fallback-model-host" data-idx="${idx}"></div>
        </label>
        <label class="field"><span class="field-label">API Key（可选）</span>
          <input type="password" class="fallback-apikey" data-idx="${idx}" placeholder="留空=使用主 Key" value="${escapeAttr(row.apiKey || '')}" autocomplete="off">
        </label>
        <label class="field"><span class="field-label">Base URL（可选）</span>
          <input type="text" class="fallback-baseurl" data-idx="${idx}" value="${escapeAttr(row.baseUrl || '')}">
        </label>
      `;
      list.appendChild(el);
      const host = el.querySelector('.fallback-model-host');
      if (typeof ModelCombobox !== 'undefined' && host) {
        row._combo = ModelCombobox.mount(host, {
          placeholder: 'model-id',
          onChange: () => {
            row.model = row._combo.getValue();
            persistChange();
          },
        });
        row._combo.setValue(row.model || '', { silent: true });
      }
      el.querySelector('.fallback-remove')?.addEventListener('click', () => {
        rows.splice(idx, 1);
        render();
        persistChange();
      });
      el.querySelector('.fallback-provider')?.addEventListener('change', (e) => {
        row.provider = e.target.value;
        persistChange();
      });
      el.querySelector('.fallback-label')?.addEventListener('input', (e) => {
        row.label = e.target.value;
        persistChange();
      });
      el.querySelector('.fallback-apikey')?.addEventListener('input', (e) => {
        row.apiKey = e.target.value;
        persistChange();
      });
      el.querySelector('.fallback-baseurl')?.addEventListener('input', (e) => {
        row.baseUrl = e.target.value;
        persistChange();
      });
    });
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function persistChange() {
    root?.dispatchEvent(new CustomEvent('fallbackchange', { bubbles: true }));
  }

  function setRows(items) {
    rows = (items || []).map((r) => ({ ...defaultRow(), ...r, _combo: null }));
    if (!rows.length) rows = [];
    render();
  }

  function getRows() {
    return rows.map((r) => ({
      provider: r.provider || getProvider(),
      model: r._combo?.getValue?.()?.trim() || r.model || '',
      apiKey: (r.apiKey || '').trim(),
      baseUrl: (r.baseUrl || '').trim(),
      label: (r.label || '').trim(),
    })).filter((r) => r.model);
  }

  function setProviders(list) {
    providers = list || [];
    render();
  }

  return { mount, setRows, getRows, setProviders };
})();
