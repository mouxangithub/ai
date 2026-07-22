/**
 * Multi-session chat storage for op助手.
 * Gateway mode: in-memory only — server (Params + WS) is the source of truth.
 */
const SessionStore = (() => {
  const LEGACY_KEY = 'openpilot-op-sessions-v1';
  const LEGACY_KEY2 = 'openpilot-op-assistant-v2';
  const LEGACY_KEY3 = 'openpilot-op-ai-chat-v1';
  const MAX_SESSIONS = 50;

  let sessions = [];
  let activeId = null;

  function uid() {
    return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function messageHasVisibleContent(msg) {
    if (!msg || typeof msg !== 'object') return false;
    if (msg.role === 'user') {
      const text = typeof msg.content === 'string'
        ? msg.content.trim()
        : (Array.isArray(msg.content)
          ? msg.content.some((p) => p?.type === 'text' && String(p.text || '').trim())
          : false);
      const hasImage = Array.isArray(msg.content)
        && msg.content.some((p) => p?.type === 'image_url');
      return Boolean(text || hasImage);
    }
    if (msg.role === 'assistant') {
      const text = typeof msg.content === 'string' ? msg.content.trim() : '';
      if (text) return true;
      if (msg.tool_calls?.length) return true;
      if (msg.reasoning_content?.trim()) return true;
    }
    return false;
  }

  function sessionHasContent(session) {
    if (!session) return false;
    const msgs = session.messages || [];
    return msgs.some(messageHasVisibleContent);
  }

  function resolveActiveId() {
    const valid = activeId && sessions.some((s) => s.id === activeId && sessionHasContent(s));
    if (!valid) {
      activeId = sessions.find(sessionHasContent)?.id ?? null;
    }
  }

  function pruneEmptySessions() {
    const prevActive = activeId;
    sessions = sessions.filter(sessionHasContent);
    if (prevActive && sessions.some((s) => s.id === prevActive)) {
      activeId = prevActive;
    } else {
      activeId = sessions[0]?.id ?? null;
    }
    resolveActiveId();
  }

  /** Gateway mode: start empty; hydrate from WS hello / GET /api/ai/sessions. */
  function init() {
    sessions = [];
    activeId = null;
  }

  /** One-time export for migrating browser localStorage → server. */
  function readLegacyLocalSnapshot() {
    for (const key of [LEGACY_KEY, LEGACY_KEY2, LEGACY_KEY3]) {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const data = JSON.parse(raw);
        if (data?.sessions?.length) {
          return {
            sessions: data.sessions,
            activeId: data.activeId ?? null,
            storageKey: key,
          };
        }
        if (Array.isArray(data) && data.length) {
          return {
            sessions: [{
              id: uid(),
              title: legacyTitle(data),
              messages: data,
              mode: 'chat',
              updatedAt: Date.now(),
            }],
            activeId: null,
            storageKey: key,
          };
        }
      } catch {}
    }
    return null;
  }

  function clearLegacyLocalStorage(keys) {
    for (const key of keys || [LEGACY_KEY, LEGACY_KEY2, LEGACY_KEY3]) {
      try { localStorage.removeItem(key); } catch {}
    }
  }

  function legacyTitle(messages) {
    const first = messages.find((m) => m.role === 'user');
    const text = typeof first?.content === 'string' ? first.content : '';
    return (text || '历史对话').slice(0, 40);
  }

  function list() {
    return [...sessions].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  }

  function listWithContent() {
    return list().filter(sessionHasContent);
  }

  function getActive() {
    if (!activeId) return null;
    return sessions.find((s) => s.id === activeId) || null;
  }

  function setActive(id) {
    if (id == null) {
      activeId = null;
      return;
    }
    if (!sessions.some((s) => s.id === id)) return;
    activeId = id;
  }

  function createSession(title) {
    const id = uid();
    const session = {
      id,
      title: (title || '新对话').slice(0, 60),
      messages: [],
      mode: 'chat',
      updatedAt: Date.now(),
    };
    sessions.unshift(session);
    activeId = id;
    while (sessions.length > MAX_SESSIONS) sessions.pop();
    return session;
  }

  function ensureSessionOnSend(previewText) {
    const existing = getActive();
    if (existing) return existing;
    const title = String(previewText || '').trim().slice(0, 40) || '新对话';
    return createSession(title);
  }

  function startDraft() {
    activeId = null;
  }

  function remove(id) {
    sessions = sessions.filter((s) => s.id !== id);
    if (activeId === id) {
      activeId = sessions[0]?.id ?? null;
    }
    resolveActiveId();
  }

  function updateMessages(id, messages, title) {
    const s = sessions.find((x) => x.id === id);
    if (!s) return;
    s.messages = messages;
    s.updatedAt = Date.now();
    if (title) s.title = title.slice(0, 60);
    else {
      const user = messages.find((m) => m.role === 'user');
      const text = typeof user?.content === 'string' ? user.content : '';
      if (text) s.title = text.slice(0, 40);
    }
  }

  function setMode(id, mode) {
    const s = sessions.find((x) => x.id === id);
    if (!s) return;
    s.mode = mode;
  }

  function getMode(id) {
    return sessions.find((x) => x.id === id)?.mode || 'chat';
  }

  function setActiveJobId(id, jobId) {
    const s = sessions.find((x) => x.id === id);
    if (!s) return;
    if (jobId) s.activeJobId = jobId;
    else delete s.activeJobId;
  }

  function getActiveJobId(id) {
    return sessions.find((x) => x.id === id)?.activeJobId || null;
  }

  function clearActiveJobId(id) {
    setActiveJobId(id, null);
  }

  function dedupeTrailingAssistants(msgs) {
    const out = Array.isArray(msgs) ? [...msgs] : [];
    const score = (m) => (
      String(m?.content || '').length
      + String(m?.reasoning_content || '').length
      + ((m?.tool_calls || []).length * 100)
    );
    while (
      out.length >= 2
      && out[out.length - 1]?.role === 'assistant'
      && out[out.length - 2]?.role === 'assistant'
    ) {
      if (score(out[out.length - 1]) >= score(out[out.length - 2])) out.splice(out.length - 2, 1);
      else out.pop();
    }
    return out;
  }

  function importMerged(nextSessions, nextActiveId) {
    const cleaned = (Array.isArray(nextSessions) ? nextSessions : [])
      .filter(sessionHasContent)
      .map((s) => ({
        ...s,
        messages: dedupeTrailingAssistants(s.messages),
      }))
      .slice(0, MAX_SESSIONS);
    sessions = cleaned;
    if (nextActiveId && sessions.some((s) => s.id === nextActiveId)) {
      activeId = nextActiveId;
    } else {
      activeId = sessions[0]?.id ?? null;
    }
    resolveActiveId();
    return sessions.length > 0;
  }

  return {
    init,
    readLegacyLocalSnapshot,
    clearLegacyLocalStorage,
    list,
    listWithContent,
    getActive,
    setActive,
    createSession,
    ensureSessionOnSend,
    startDraft,
    remove,
    updateMessages,
    setMode,
    getMode,
    setActiveJobId,
    getActiveJobId,
    clearActiveJobId,
    importMerged,
    sessionHasContent,
    get activeId() { return activeId; },
  };
})();
