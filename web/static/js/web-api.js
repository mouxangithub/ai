/**
 * REST API helper — PIN headers, retry, JSON parse.
 */
const WebApi = (() => {
  let pinRequired = false;
  let pinModalEls = null;
  let onPinSuccess = () => {};

  function configure(opts = {}) {
    pinRequired = !!opts.pinRequired;
    pinModalEls = opts.els || null;
    onPinSuccess = typeof opts.onPinSuccess === 'function' ? opts.onPinSuccess : () => {};
  }

  function getApiHeaders() {
    const h = {};
    const pin = sessionStorage.getItem('ai-web-pin');
    if (pin) h['X-AI-Pin'] = pin;
    if (typeof DeviceTrust !== 'undefined') {
      Object.assign(h, DeviceTrust.headers());
    }
    return h;
  }

  function promptForPin() {
    return new Promise((resolve) => {
      const els = pinModalEls;
      if (!els?.pinModal) return resolve(false);
      els.pinModal.hidden = false;
      if (typeof syncBodyScrollLock === 'function') syncBodyScrollLock();
      els.pinModalInput.value = '';
      const done = (ok) => {
        els.pinModal.hidden = true;
        if (typeof syncBodyScrollLock === 'function') syncBodyScrollLock();
        els.pinModalOk.removeEventListener('click', onOk);
        resolve(ok);
      };
      const onOk = () => {
        const v = els.pinModalInput.value.trim();
        if (!v) return done(false);
        sessionStorage.setItem('ai-web-pin', v);
        onPinSuccess();
        done(true);
      };
      els.pinModalOk.addEventListener('click', onOk);
    });
  }

  async function api(method, path, body, opts = {}) {
    const ac = opts.timeoutMs ? new AbortController() : null;
    let timer;
    const fetchOpts = { method, headers: getApiHeaders() };
    if (ac) fetchOpts.signal = ac.signal;
    if (body) {
      fetchOpts.headers['Content-Type'] = 'application/json';
      fetchOpts.body = JSON.stringify(body);
    }
    if (ac) timer = setTimeout(() => ac.abort(), opts.timeoutMs);
    try {
      const res = await fetch(path, fetchOpts);
      if (res.status === 401 && pinRequired) {
        const ok = await promptForPin();
        if (ok) return api(method, path, body, opts);
      }
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = { ok: false, error: text }; }
      return { status: res.status, data };
    } catch (e) {
      if (e?.name === 'AbortError') {
        return { status: 0, data: { ok: false, error: 'request timeout' } };
      }
      throw e;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  return { configure, api, getApiHeaders, promptForPin };
})();
