/**
 * Chat job streaming — SSE/WS events, poll fallback, attach on refresh.
 */
const ChatJobs = (() => {
  let deps = {};
  const contexts = new Map();
  let pollTimer = null;
  let activeJobId = null;

  function init(d) {
    deps = d;
  }

  function getActiveJobId() {
    return activeJobId;
  }

  function setActiveJobId(id) {
    activeJobId = id;
  }

  function findCtx(jobId, sessionId) {
    let ctx = contexts.get(jobId);
    if (ctx) return ctx;
    const pendingKey = `pending:${sessionId}`;
    ctx = contexts.get(pendingKey);
    if (ctx) return ctx;
    for (const [, candidate] of contexts.entries()) {
      if (candidate.sessionId === sessionId) return candidate;
    }
    return null;
  }

  function registerCtx(jobId, sessionId, ctx) {
    contexts.delete(`pending:${sessionId}`);
    contexts.set(jobId, ctx);
  }

  function abortActive() {
    const jobId = activeJobId || deps.SessionStore?.getActiveJobId(deps.SessionStore.activeId);
    if (jobId) {
      deps.api('DELETE', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}`).catch(() => {});
      deps.SessionStore?.clearActiveJobId(deps.SessionStore.activeId);
      deps.syncSessionsToDevice?.().catch(() => {});
    }
    if (deps.getAbortController?.()) {
      const ac = deps.getAbortController();
      if (typeof ac.abort === 'function') ac.abort();
      else ac.cancelled = true;
    }
    deps.endChatStream?.(deps.getStreamSessionId?.());
  }

  function endPoll() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  async function handleStreamEvent(data, ctx) {
    const ui = deps.reconcileStreamUi(ctx);
    const { assistantMessage, streamActive } = ctx;
    if (!streamActive()) return 'stop';

    deps.handleAgentStreamEvent?.(data, ctx);

    if (data.type === 'error') {
      deps.hideAssistantLoading(ui);
      ui.content.textContent = deps.formatApiError(data.error);
      assistantMessage.content = ui.content.textContent;
      return 'error';
    }

    if (data.type === 'reasoning') {
      deps.hideAssistantLoading(ui);
      if (!ctx.thinkingStarted) {
        ctx.thinkingStarted = true;
        ui.thinking.classList.remove('hidden');
        ui.thinkingLabel.textContent = deps.t('thinkingActive', 'Thinking…');
      }
      assistantMessage.reasoning_content += data.delta;
      ui.thinkingBody.textContent += data.delta;
      deps.scrollToBottom();
    }

    if (data.type === 'content') {
      deps.hideAssistantLoading(ui);
      if (ctx.thinkingStarted) {
        ui.thinking.classList.add('collapsed');
        ui.thinkingLabel.textContent = deps.t('thinking', 'Thinking');
      }
      ctx.contentStarted = true;
      ctx.rawContent = (ctx.rawContent || '') + (data.delta || '');
      const clean = typeof deps.stripLeakedToolCalls === 'function'
        ? deps.stripLeakedToolCalls(ctx.rawContent)
        : ctx.rawContent;
      const prevLen = ctx.displayedContentLen || 0;
      const newPart = clean.slice(prevLen);
      ctx.displayedContentLen = clean.length;
      assistantMessage.content = clean;
      if (newPart) {
        if (typeof Markdown !== 'undefined' && ui.content.classList.contains('md-content')) {
          ui.content.textContent = clean;
        } else {
          ui.content.textContent = clean;
        }
      } else if (!clean && ui.content.textContent) {
        ui.content.textContent = '';
      }
      deps.scrollToBottom();
    }

    if (data.type === 'tool_call') {
      deps.hideAssistantLoading(ui);
      if (ctx.thinkingStarted) {
        ui.thinking.classList.add('collapsed');
        ui.thinkingLabel.textContent = deps.t('thinking', 'Thinking');
      } else {
        ui.thinking.classList.add('hidden');
      }
      ui.toolsBlock.classList.remove('hidden');
      deps.renderToolCall(ui.toolsList, data.id, data.name, data.arguments, null, data.agentId || data.agent_id);
      deps.updateToolCallsSummary(ui.toolsBlock);
      if (!assistantMessage.tool_calls.some((tc) => tc.id === data.id)) {
        assistantMessage.tool_calls.push({
          id: data.id,
          type: 'function',
          function: { name: data.name, arguments: data.arguments },
        });
      }
    }

    if (data.type === 'tool_result') {
      deps.hideAssistantLoading(ui);
      let result = data.result;
      if (result?.needs_confirmation && result.pending_id) {
        const { data: confirmed } = await deps.api('POST', '/api/ai/write/confirm', { pending_id: result.pending_id });
        result = confirmed;
      }
      assistantMessage.tool_results[data.id] = result;
      deps.updateToolCallResult(ui.toolsList, data.id, result);
    }

    if (data.type === 'canvas' && typeof CanvasPanel !== 'undefined') {
      CanvasPanel.addArtifact(ctx.sessionId, data.artifact);
    }

    if (data.type === 'usage') {
      deps.renderUsage?.(ui.wrapper, data.usage);
      if (deps.els?.settingsSidebar?.classList.contains('open')) deps.loadUsage?.();
      if (typeof OfficePanel !== 'undefined' && OfficePanel.isOpen()) {
        OfficePanel.setUsageTokens(data.usage?.total_tokens || 0);
      }
    }

    if (data.type === 'done') {
      deps.hideAssistantLoading(ui);
      deps.syncThinkingBlock(ui, assistantMessage);
      if (data.resolvedModel) deps.updateModelBadge?.(data.resolvedModel);
    }

    return 'continue';
  }

  async function finalizeCtx(jobId, sessionId, ctx, status, payload = {}) {
    contexts.delete(jobId);
    const streamActive = ctx.streamActive;
    deps.clearLiveStreamChrome?.(ctx.ui);
    if (status === 'done' && streamActive()) {
      deps.finishAssistant(ctx.ui, ctx.assistantMessage, sessionId);
    } else if (status === 'error' && streamActive()) {
      ctx.assistantMessage.content = deps.formatApiError(payload.error || 'Error');
      deps.finishAssistant(ctx.ui, ctx.assistantMessage, sessionId);
    } else if (status === 'cancelled' && streamActive() && ctx.ui.wrapper?.isConnected) {
      ctx.ui.wrapper.remove();
    } else if (status === 'done' && deps.SessionStore?.activeId === sessionId) {
      deps.endChatStream?.(sessionId);
      deps.commitAssistantMessage?.(sessionId, deps.normalizeStoredMessage({
        role: 'assistant',
        ...(payload.assistant || ctx.assistantMessage),
      }));
      deps.renderStoredMessages?.();
      deps.SessionStore?.clearActiveJobId(sessionId);
      deps.syncSessionsToDevice?.().catch(() => {});
      return;
    }
    deps.SessionStore?.clearActiveJobId(sessionId);
    deps.endChatStream?.(sessionId);
    deps.syncSessionsToDevice?.().catch(() => {});
  }

  function pollDelayMs() {
    return deps.isSyncWsConnected?.() ? 1200 : 400;
  }

  async function applyTerminalJobState(jobId, sessionId, ctx, status, payload = {}) {
    if (ctx) {
      await finalizeCtx(jobId, sessionId, ctx, status, payload);
      return;
    }
    contexts.delete(jobId);
    deps.SessionStore?.clearActiveJobId(sessionId);
    if (deps.SessionStore?.activeId !== sessionId) return;
    if (status === 'done') {
      const assistant = deps.normalizeStoredMessage({
        role: 'assistant',
        content: '',
        reasoning_content: '',
        tool_calls: [],
        tool_results: {},
        ...(payload.assistant || {}),
      });
      if (deps.assistantMessageHasContent?.(assistant)) {
        deps.commitAssistantMessage?.(sessionId, assistant);
        deps.renderStoredMessages?.();
      }
    }
    deps.endChatStream?.(sessionId);
    deps.syncSessionsToDevice?.().catch(() => {});
  }

  async function handleSyncWsEvent(payload) {
    const { jobId, sessionId, event, status } = payload;
    let ctx = findCtx(jobId, sessionId);
    if (ctx && !contexts.has(jobId)) {
      registerCtx(jobId, sessionId, ctx);
    }
    if (!ctx && deps.SessionStore?.activeId === sessionId) {
      deps.SessionStore.setActiveJobId(sessionId, jobId);
      await attach(sessionId, jobId, {
        assistant: payload.assistant,
        events: event ? [event] : [],
        nextSince: payload.nextSince || 0,
        status: status || 'running',
      });
      ctx = findCtx(jobId, sessionId);
    }
    if (!ctx) {
      if (['done', 'error', 'cancelled'].includes(status)) {
        await applyTerminalJobState(jobId, sessionId, null, status, payload);
      }
      return;
    }

    if (event) {
      const seq = event._seq || 0;
      if (seq <= (ctx.lastSeq || 0)) {
        if (['done', 'error', 'cancelled'].includes(status)) {
          await finalizeCtx(jobId, sessionId, ctx, status, payload);
        }
        return;
      }
      ctx.lastSeq = seq;
      const result = await handleStreamEvent(event, ctx);
      if (result === 'error') {
        await finalizeCtx(jobId, sessionId, ctx, 'error', payload);
        return;
      }
      if (ctx.streamActive()) deps.savePartialAssistant?.(sessionId, ctx.assistantMessage);
    }

    if (['done', 'error', 'cancelled'].includes(status)) {
      await finalizeCtx(jobId, sessionId, ctx, status, payload);
    }
  }

  function watch(jobId, sessionId, ctx) {
    ctx.lastSeq = Math.max(ctx.lastSeq || 0, ctx.since || 0);
    ctx.since = ctx.lastSeq;
    ctx._pollActive = false;
    registerCtx(jobId, sessionId, ctx);
    poll(jobId, sessionId, ctx);
  }

  function poll(jobId, sessionId, ctx) {
    ctx._pollActive = true;
    let since = ctx.since || 0;
    let finished = false;

    const tick = async () => {
      if (finished) return;

      try {
        const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=${since}`);
        if (!data?.ok) {
          if (deps.SessionStore?.getActiveJobId(sessionId) === jobId) {
            deps.SessionStore?.clearActiveJobId(sessionId);
            if (deps.SessionStore?.activeId === sessionId) deps.endChatStream?.(sessionId);
          }
          finished = true;
          contexts.delete(jobId);
          return;
        }

        const streamActive = ctx.streamActive;
        for (const ev of data.events || []) {
          since = Math.max(since, ev._seq || since);
          ctx.since = since;
          ctx.lastSeq = since;
          const result = await handleStreamEvent(ev, ctx);
          if (result === 'error') {
            finished = true;
            await applyTerminalJobState(jobId, sessionId, ctx, 'error', data);
            return;
          }
          if (result === 'stop') break;
        }

        if (streamActive()) deps.savePartialAssistant?.(sessionId, ctx.assistantMessage);

        if (['done', 'error', 'cancelled'].includes(data.status)) {
          finished = true;
          await applyTerminalJobState(jobId, sessionId, ctx, data.status, data);
          return;
        }

        pollTimer = setTimeout(tick, pollDelayMs());
      } catch {
        if (!finished) pollTimer = setTimeout(tick, pollDelayMs());
      }
    };

    tick();
  }

  async function stream(messages) {
    const sessionId = deps.SessionStore.activeId;
    deps.setStreamSessionId?.(sessionId);
    const abortController = { cancelled: false };
    deps.setAbortController?.(abortController);
    if (deps.els?.sendBtn) deps.els.sendBtn.textContent = deps.t('stop', 'Stop');

    const streamActive = () => (
      deps.SessionStore.activeId === sessionId
      && deps.getAbortController?.()
      && !deps.getAbortController().cancelled
    );

    const hasImages = messages.some(
      (m) => m.role === 'user' && Array.isArray(m.content) && m.content.some((p) => p.type === 'image_url'),
    );
    const useTools = !hasImages;
    const workflowId = deps.consumePendingWorkflow?.() || '';

    const ui = deps.appendAssistantMessage();
    deps.showAssistantLoading(ui);
    deps.markLiveStreamUi(ui);
    const assistantMessage = {
      role: 'assistant',
      content: '',
      reasoning_content: '',
      tool_calls: [],
      tool_results: {},
      agent_events: [],
    };

    const ctx = {
      ui,
      assistantMessage,
      sessionId,
      streamActive,
      thinkingStarted: false,
      contentStarted: false,
      rawContent: '',
      displayedContentLen: 0,
      since: 0,
    };
    contexts.set(`pending:${sessionId}`, ctx);

    try {
      const idempotencyKey = `send-${sessionId}-${Date.now()}`;
      const queueExtras = (typeof CommandQueue !== 'undefined' && deps.getState?.()?.driving)
        ? CommandQueue.payloadExtras(true)
        : {};
      const { data: startData } = await deps.api('POST', '/api/ai/chat/jobs', {
        sessionId,
        idempotencyKey,
        messages: deps.prepareMessagesForApi(messages),
        tools: useTools,
        mode: deps.chatMode || 'unlimited',
        workflow: workflowId || undefined,
        maxToolRounds: 'infinite',
        ...queueExtras,
      });

      if (!startData?.ok) {
        contexts.delete(`pending:${sessionId}`);
        if (!streamActive()) return;
        deps.hideAssistantLoading(ui);
        ui.content.textContent = deps.formatApiError(startData?.error || 'Failed to start chat job');
        assistantMessage.content = ui.content.textContent;
        deps.finishAssistant(ui, assistantMessage, sessionId);
        deps.endChatStream?.(sessionId);
        return;
      }

      if (startData.queued || startData.action === 'collected') {
        contexts.delete(`pending:${sessionId}`);
        if (!streamActive()) return;
        deps.hideAssistantLoading(ui);
        const pos = startData.queuePosition || startData.collectBatch || '?';
        const msg = startData.action === 'collected'
          ? `已合并入批处理队列（${pos} 条）`
          : `已加入行驶队列（位置 ${pos}）`;
        ui.content.textContent = msg;
        assistantMessage.content = ui.content.textContent;
        deps.finishAssistant(ui, assistantMessage, sessionId);
        deps.endChatStream?.(sessionId);
        deps.showToast?.('消息已排队，当前任务完成后继续');
        return;
      }

      if (!startData.jobId) {
        contexts.delete(`pending:${sessionId}`);
        if (!streamActive()) return;
        deps.hideAssistantLoading(ui);
        ui.content.textContent = deps.formatApiError('Failed to start chat job');
        assistantMessage.content = ui.content.textContent;
        deps.finishAssistant(ui, assistantMessage, sessionId);
        deps.endChatStream?.(sessionId);
        return;
      }

      const jobId = startData.jobId;
      activeJobId = jobId;
      deps.SessionStore.setActiveJobId(sessionId, jobId);
      deps.syncSessionsToDevice?.().catch(() => {});
      watch(jobId, sessionId, ctx);
    } catch (err) {
      contexts.delete(`pending:${sessionId}`);
      if (streamActive()) {
        deps.hideAssistantLoading(ui);
        ui.content.textContent = `Error: ${err.message}`;
        assistantMessage.content = ui.content.textContent;
        deps.finishAssistant(ui, assistantMessage, sessionId);
      } else if (ui.wrapper?.isConnected) {
        ui.wrapper.remove();
      }
      deps.endChatStream?.(sessionId);
    }
  }

  async function attach(sessionId, jobId, initialData) {
    if (activeJobId === jobId && deps.getAbortController?.()) return;
    if (deps.isLocallyStreaming?.(sessionId) && findCtx(jobId, sessionId)) return;

    const messages = deps.getCurrentMessages?.() || [];
    const last = messages[messages.length - 1];
    let ui;
    let assistantMessage;

    if (last?.role === 'assistant' && deps.assistantMessageHasContent?.(last)) {
      ui = deps.getLiveStreamUi?.() || deps.getLastAssistantUi?.() || deps.appendAssistantMessage();
      assistantMessage = deps.normalizeStoredMessage({ ...last });
      deps.hydrateAssistantUi?.(ui, assistantMessage);
    } else if (last?.role === 'user') {
      ui = deps.getLiveStreamUi?.() || deps.appendAssistantMessage();
      if (!deps.getLiveStreamUi?.()) deps.showAssistantLoading(ui);
      assistantMessage = {
        role: 'assistant',
        content: '',
        reasoning_content: '',
        tool_calls: [],
        tool_results: {},
        agent_events: [],
        ...(initialData?.assistant || {}),
      };
      if (initialData?.assistant) deps.hydrateAssistantUi?.(ui, assistantMessage);
    } else if (last?.role === 'assistant') {
      ui = deps.getLiveStreamUi?.() || deps.appendAssistantMessage();
      if (!deps.getLiveStreamUi?.()) deps.showAssistantLoading(ui);
      assistantMessage = {
        role: 'assistant',
        content: '',
        reasoning_content: '',
        tool_calls: [],
        tool_results: {},
        agent_events: [],
        ...(initialData?.assistant || {}),
      };
      if (initialData?.assistant) deps.hydrateAssistantUi?.(ui, assistantMessage);
    } else {
      return;
    }

    deps.markLiveStreamUi(ui);
    deps.setStreamSessionId?.(sessionId);
    deps.setAbortController?.({ cancelled: false });
    activeJobId = jobId;
    if (deps.els?.sendBtn) deps.els.sendBtn.textContent = deps.t('stop', 'Stop');

    const since = initialData?.nextSince || 0;
    const streamCtx = {
      ui,
      assistantMessage,
      sessionId,
      streamActive: () => (
        deps.SessionStore.activeId === sessionId
        && deps.getAbortController?.()
        && !deps.getAbortController().cancelled
      ),
      thinkingStarted: Boolean(assistantMessage.reasoning_content),
      contentStarted: Boolean(assistantMessage.content),
      rawContent: assistantMessage.content || '',
      displayedContentLen: (assistantMessage.content || '').length,
      since,
      lastSeq: since,
    };

    if (initialData?.events?.length) {
      for (const ev of initialData.events) {
        const seq = ev._seq || 0;
        if (seq <= streamCtx.lastSeq) continue;
        streamCtx.lastSeq = seq;
        await handleStreamEvent(ev, streamCtx);
      }
    }

    watch(jobId, sessionId, streamCtx);
  }

  async function syncActiveSession() {
    const sessionId = deps.SessionStore?.activeId;
    if (!sessionId) return;
    if (deps.isChatUiLocked?.()) return;

    let jobId = deps.SessionStore.getActiveJobId(sessionId);
    if (!jobId) {
      const { data: listData } = await deps.api('GET', `/api/ai/chat/jobs?sessionId=${encodeURIComponent(sessionId)}`);
      jobId = listData?.jobs?.[0]?.id;
      if (jobId) deps.SessionStore.setActiveJobId(sessionId, jobId);
    }
    if (!jobId) return;
    if (activeJobId === jobId && deps.getAbortController?.()) return;

    const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=0`);
    if (!data?.ok) {
      deps.SessionStore.clearActiveJobId(sessionId);
      return;
    }

    if (data.status === 'done') {
      deps.commitAssistantMessage?.(sessionId, deps.normalizeStoredMessage({
        role: 'assistant',
        content: '',
        reasoning_content: '',
        tool_calls: [],
        tool_results: {},
        ...(data.assistant || {}),
      }));
      deps.SessionStore.clearActiveJobId(sessionId);
      deps.renderStoredMessages?.();
      deps.syncSessionsToDevice?.().catch(() => {});
      return;
    }

    if (data.status !== 'running') {
      deps.SessionStore.clearActiveJobId(sessionId);
      return;
    }

    await attach(sessionId, jobId, data);
  }

  function forEachPollingCtx(fn) {
    for (const [jobId, ctx] of contexts.entries()) {
      if (!ctx._pollActive) fn(jobId, ctx);
    }
  }

  function resumePolling() {
    for (const [jobId, ctx] of contexts.entries()) {
      if (!ctx._pollActive && ctx.sessionId) poll(jobId, ctx.sessionId, ctx);
    }
  }

  async function recoverStuckStreams() {
    const sessionId = deps.SessionStore?.activeId;
    if (!sessionId) {
      if (deps.getAbortController?.() && !contexts.size) deps.endChatStream?.();
      return;
    }

    let jobId = deps.SessionStore.getActiveJobId(sessionId) || activeJobId;
    if (!jobId) {
      if (deps.getAbortController?.() && !contexts.size) deps.endChatStream?.(sessionId);
      return;
    }

    const ctx = findCtx(jobId, sessionId);
    if (ctx && !ctx._pollActive) poll(jobId, sessionId, ctx);

    const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=0`);
    if (!data?.ok) {
      deps.SessionStore.clearActiveJobId(sessionId);
      if (deps.SessionStore.activeId === sessionId) deps.endChatStream?.(sessionId);
      return;
    }

    if (data.status === 'running') {
      if (!ctx && deps.SessionStore.activeId === sessionId) {
        await attach(sessionId, jobId, data);
      }
      return;
    }

    if (['done', 'error', 'cancelled'].includes(data.status)) {
      await applyTerminalJobState(jobId, sessionId, ctx, data.status, data);
    }
  }

  return {
    init,
    stream,
    attach,
    syncActiveSession,
    handleSyncWsEvent,
    abortActive,
    findCtx,
    getActiveJobId,
    setActiveJobId,
    endPoll,
    forEachPollingCtx,
    resumePolling,
    recoverStuckStreams,
  };
})();
