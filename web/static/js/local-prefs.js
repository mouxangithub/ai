/**
 * Client UI preferences — Gateway mode: config/models truth on server (WS hello).
 * Only unsaved config draft uses sessionStorage; tool/theme prefs stay local.
 */
const LocalPrefs = (() => {
  const CONFIG_DRAFT = 'openpilot-ai-config-draft';
  const TOOL_PREFS = 'openpilot-ai-tool-prefs';
  const TOOL_DRIVING_PREFS = 'openpilot-ai-tool-driving-prefs';
  const MODEL_PROFILE = 'openpilot-ai-model-profile';

  let _serverToolDefaults = null;
  let _configCache = null;
  let _modelsCache = {};

  function readJson(storage, key, fallback) {
    try {
      const raw = storage.getItem(key);
      if (raw) return JSON.parse(raw);
    } catch {}
    return fallback;
  }

  function writeJson(storage, key, value) {
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch {}
  }

  function setServerToolDefaults(toolMeta) {
    if (!toolMeta || typeof toolMeta !== 'object') return;
    _serverToolDefaults = toolMeta;
  }

  function buildDefaultTools() {
    const out = {};
    const meta = _serverToolDefaults || {};
    for (const [name, info] of Object.entries(meta)) {
      out[name] = !!info.default_enabled;
    }
    if (!Object.keys(out).length) {
      return {
        get_vehicle_state: true,
        read_params: true,
        list_dp_settings: true,
        run_shell: true,
      };
    }
    return out;
  }

  function buildDefaultDrivingTools() {
    const out = {};
    const meta = _serverToolDefaults || {};
    for (const [name, info] of Object.entries(meta)) {
      if (info.driving) out[name] = true;
    }
    return out;
  }

  function getConfigCache() {
    return _configCache;
  }

  function setConfigCache(config) {
    _configCache = config ? { ...config, cachedAt: Date.now() } : null;
  }

  function clearConfigCache() {
    _configCache = null;
  }

  function getConfigDraft() {
    return readJson(sessionStorage, CONFIG_DRAFT, null);
  }

  function setConfigDraft(draft) {
    if (draft) writeJson(sessionStorage, CONFIG_DRAFT, { ...draft, draftAt: Date.now() });
  }

  function clearConfigDraft() {
    try { sessionStorage.removeItem(CONFIG_DRAFT); } catch {}
  }

  function mergeDraftOntoServer(server, draft) {
    const base = { ...(server || {}) };
    if (!draft) return base;
    for (const [k, v] of Object.entries(draft)) {
      if (k.startsWith('_') || k === 'cachedAt' || k === 'draftAt') continue;
      if (v === undefined || v === null) continue;
      if (k === 'apiKey' || k === 'embeddingApiKey' || k === 'webPin') {
        if (v && !String(v).startsWith('•')) base[k] = v;
        continue;
      }
      base[k] = v;
    }
    return base;
  }

  function mergeConfigLayers(server, _cache, draft) {
    return mergeDraftOntoServer(server, draft);
  }

  function getModelsCache(provider) {
    return _modelsCache[provider] || null;
  }

  function setModelsCache(provider, models) {
    _modelsCache[provider] = { models, cachedAt: Date.now() };
  }

  function clearModelsCache() {
    _modelsCache = {};
  }

  function getToolPrefs() {
    const defaults = buildDefaultTools();
    return { ...defaults, ...readJson(localStorage, TOOL_PREFS, {}) };
  }

  function getToolDrivingPrefs() {
    const defaults = buildDefaultDrivingTools();
    return { ...defaults, ...readJson(localStorage, TOOL_DRIVING_PREFS, {}) };
  }

  function setToolPrefs(prefs) {
    writeJson(localStorage, TOOL_PREFS, { ...buildDefaultTools(), ...prefs });
  }

  function setToolDrivingPrefs(prefs) {
    writeJson(localStorage, TOOL_DRIVING_PREFS, { ...buildDefaultDrivingTools(), ...prefs });
  }

  function getMaxToolRounds() {
    return 'infinite';
  }

  function setMaxToolRounds(_value) {
    /* fixed ∞ — no UI */
  }

  function getModelProfile() {
    const v = localStorage.getItem(MODEL_PROFILE);
    return v === 'fast' || v === 'deep' ? v : 'auto';
  }

  function setModelProfile(profile) {
    const v = profile === 'fast' || profile === 'deep' ? profile : 'auto';
    try {
      localStorage.setItem(MODEL_PROFILE, v);
    } catch {}
    return v;
  }

  return {
    getConfigCache,
    setConfigCache,
    clearConfigCache,
    getConfigDraft,
    setConfigDraft,
    clearConfigDraft,
    mergeDraftOntoServer,
    mergeConfigLayers,
    getModelsCache,
    setModelsCache,
    clearModelsCache,
    setServerToolDefaults,
    getToolPrefs,
    getToolDrivingPrefs,
    setToolPrefs,
    setToolDrivingPrefs,
    getMaxToolRounds,
    setMaxToolRounds,
    getModelProfile,
    setModelProfile,
    buildDefaultTools,
  };
})();
