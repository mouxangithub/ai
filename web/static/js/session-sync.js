/**
 * Gateway session sync — server-first conflict resolution (OpenClaw-style).
 * stateVersion tracked in memory; no localStorage for session truth.
 */
const SessionSync = (() => {
  let serverStateVersion = 0;
  let serverSavedAt = 0;

  let localDirtyVersion = 0;
  let lastLocalMutationAt = 0;

  function setServerSyncMeta(data) {
    const version = Number(data?.stateVersion || data?.savedAt) || 0;
    const savedAt = Number(data?.savedAt) || 0;
    if (version) serverStateVersion = Math.max(serverStateVersion, version);
    if (savedAt) serverSavedAt = Math.max(serverSavedAt, savedAt);
  }

  function getServerStateVersion() {
    return serverStateVersion;
  }

  function getServerSavedAt() {
    return serverSavedAt;
  }

  function markLocalDirty() {
    localDirtyVersion += 1;
    lastLocalMutationAt = Date.now();
  }

  function clearLocalDirty() {
    localDirtyVersion = 0;
  }

  function isLocallyDirty(withinMs = 4000) {
    return localDirtyVersion > 0 && (Date.now() - lastLocalMutationAt) < withinMs;
  }

  function messagesContentScore(msgs) {
    if (!Array.isArray(msgs)) return 0;
    let score = msgs.length * 1000;
    for (const m of msgs) {
      const text = typeof m?.content === 'string' ? m.content : '';
      score += text.length;
      if (m?.reasoning_content) score += String(m.reasoning_content).length;
      if (m?.tool_calls?.length) score += m.tool_calls.length * 50;
    }
    return score;
  }

  function pickSessionMessages(a, b) {
    const aMsgs = Array.isArray(a.messages) ? a.messages : [];
    const bMsgs = Array.isArray(b.messages) ? b.messages : [];
    if (aMsgs.length !== bMsgs.length) {
      return aMsgs.length > bMsgs.length ? aMsgs : bMsgs;
    }
    const aScore = messagesContentScore(aMsgs);
    const bScore = messagesContentScore(bMsgs);
    if (aScore !== bScore) {
      return aScore > bScore ? aMsgs : bMsgs;
    }
    return (Number(a.updatedAt) || 0) >= (Number(b.updatedAt) || 0) ? aMsgs : bMsgs;
  }

  /** Server wins when its stateVersion is newer (Gateway authoritative). */
  function shouldTakeRemoteAuthoritative(data) {
    const remoteV = Number(data?.stateVersion || data?.savedAt) || 0;
    if (!remoteV) return false;
    if (serverStateVersion === 0) return true;
    return remoteV > serverStateVersion;
  }

  function mergeSessionRecords(remoteSessions, localSessions, sessionHasContent, opts = {}) {
    if (opts.remoteAuthoritative && remoteSessions.length) {
      return remoteSessions
        .filter((s) => sessionHasContent(s))
        .map((s) => ({
          ...s,
          mode: s.mode || 'chat',
          messages: Array.isArray(s.messages) ? s.messages : [],
          updatedAt: Number(s.updatedAt) || 0,
        }))
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    }
    const byId = new Map();
    const normalize = (s) => ({
      ...s,
      mode: s.mode || 'chat',
      messages: Array.isArray(s.messages) ? s.messages : [],
      updatedAt: Number(s.updatedAt) || 0,
    });

    for (const rs of remoteSessions) {
      const n = normalize(rs);
      if (!sessionHasContent(n)) continue;
      byId.set(rs.id, n);
    }

    for (const ls of localSessions) {
      const n = normalize(ls);
      if (!sessionHasContent(n)) continue;
      const prev = byId.get(ls.id);
      if (!prev) {
        byId.set(ls.id, n);
        continue;
      }

      const localScore = messagesContentScore(ls.messages);
      const remoteScore = messagesContentScore(prev.messages);
      const localNewer = (ls.updatedAt || 0) > (prev.updatedAt || 0);
      const localRicher = localScore > remoteScore;
      const preferLocalMeta = localNewer || localRicher;

      const messages = pickSessionMessages(
        { messages: ls.messages, updatedAt: ls.updatedAt || 0 },
        { messages: prev.messages, updatedAt: prev.updatedAt || 0 },
      );
      const newer = preferLocalMeta ? ls : prev;

      byId.set(ls.id, {
        ...prev,
        mode: prev.mode || ls.mode || 'chat',
        messages,
        title: preferLocalMeta && ls.title ? ls.title : (prev.title || ls.title),
        updatedAt: Math.max(ls.updatedAt || 0, prev.updatedAt || 0),
        activeJobId: newer.activeJobId || prev.activeJobId || ls.activeJobId || null,
      });
    }

    return [...byId.values()].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  }

  function shouldSkipRemoteMerge(ctx) {
    const { data, isLocallyStreaming, hasActiveChatJob } = ctx;
    if (typeof isLocallyStreaming === 'function' && isLocallyStreaming()) return true;
    if (typeof hasActiveChatJob === 'function' && hasActiveChatJob()) return true;

    const remoteSavedAt = Number(data?.savedAt) || 0;
    if (isLocallyDirty() && remoteSavedAt <= serverSavedAt) return true;
    return false;
  }

  function pickActiveId({
    merged,
    data,
    localHasContent,
    remoteSessions,
    localActiveBefore,
  }) {
    const remoteSavedAt = Number(data?.savedAt) || 0;

    if (!localHasContent && remoteSessions.length) {
      return data.activeId && merged.some((s) => s.id === data.activeId)
        ? data.activeId
        : merged[0].id;
    }
    if (localActiveBefore && merged.some((s) => s.id === localActiveBefore)) {
      return localActiveBefore;
    }
    if (remoteSavedAt > serverSavedAt && data.activeId && merged.some((s) => s.id === data.activeId)) {
      return data.activeId;
    }
    if (data.activeId && merged.some((s) => s.id === data.activeId)) {
      return data.activeId;
    }
    return merged[0].id;
  }

  return {
    setServerSyncMeta,
    getServerStateVersion,
    getServerSavedAt,
    markLocalDirty,
    clearLocalDirty,
    isLocallyDirty,
    pickSessionMessages,
    mergeSessionRecords,
    shouldSkipRemoteMerge,
    pickActiveId,
    shouldTakeRemoteAuthoritative,
  };
})();
