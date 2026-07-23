/**
 * Hermes-style terminal AI — natural language routes to op助手.
 * AI replies render in #terminalAiFeed (DOM); shell stays in xterm only.
 */
const TerminalAi = (() => {
  let deps = {};
  let running = false;
  let activeJobId = null;
  let lineBuffer = '';
  let feedEl = null;
  let paneEl = null;

  function init(d = {}) {
    deps = d;
    feedEl = document.getElementById('terminalAiFeed');
    paneEl = document.getElementById('terminalAiPane');
    const clearBtn = document.getElementById('terminalAiPaneClear');
    if (clearBtn && !clearBtn.dataset.bound) {
      clearBtn.dataset.bound = '1';
      clearBtn.addEventListener('click', () => clearFeed());
    }
  }

  function isRunning() {
    return running;
  }

  function ensureFeed() {
    if (!feedEl) feedEl = document.getElementById('terminalAiFeed');
    if (!paneEl) paneEl = document.getElementById('terminalAiPane');
    return feedEl;
  }

  function showPane() {
    if (paneEl) paneEl.removeAttribute('hidden');
  }

  function clearFeed() {
    if (feedEl) feedEl.innerHTML = '';
    if (paneEl && (!feedEl || !feedEl.children.length)) {
      paneEl.setAttribute('hidden', '');
    }
  }

  function scrollFeed() {
    if (!feedEl) return;
    requestAnimationFrame(() => {
      feedEl.scrollTop = feedEl.scrollHeight;
    });
  }

  function createTurn(query) {
    const feed = ensureFeed();
    if (!feed) return null;
    showPane();

    const turn = document.createElement('div');
    turn.className = 'terminal-ai-turn';

    const userEl = document.createElement('div');
    userEl.className = 'terminal-ai-turn-user';
    userEl.textContent = query;

    const assistantEl = document.createElement('div');
    assistantEl.className = 'terminal-ai-turn-assistant';

    const statusEl = document.createElement('div');
    statusEl.className = 'terminal-ai-status';
    statusEl.textContent = '处理中…';

    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'terminal-ai-thinking';
    thinkingEl.hidden = true;
    thinkingEl.innerHTML = '<span class="terminal-ai-thinking-label">思考</span><span class="terminal-ai-thinking-body"></span>';

    const contentEl = document.createElement('div');
    contentEl.className = 'terminal-ai-content';
    contentEl.hidden = true;

    const toolsEl = document.createElement('div');
    toolsEl.className = 'terminal-ai-tools';

    assistantEl.append(statusEl, thinkingEl, contentEl, toolsEl);
    turn.append(userEl, assistantEl);
    feed.appendChild(turn);
    scrollFeed();

    return {
      statusEl,
      thinkingEl,
      thinkingBody: thinkingEl.querySelector('.terminal-ai-thinking-body'),
      contentEl,
      toolsEl,
      finish(statusText) {
        if (statusEl) statusEl.remove();
        if (statusText) {
          const s = document.createElement('div');
          s.className = 'terminal-ai-status';
          s.textContent = statusText;
          assistantEl.insertBefore(s, assistantEl.firstChild);
        }
        scrollFeed();
      },
      setError(msg) {
        if (statusEl) statusEl.remove();
        const err = document.createElement('div');
        err.className = 'terminal-ai-error';
        err.textContent = msg;
        assistantEl.appendChild(err);
        scrollFeed();
      },
    };
  }

  function shouldRouteToAi(line) {
    const t = (line || '').trim();
    if (!t) return false;
    if (t.startsWith('!')) return false;
    if (t.startsWith('?') || t.startsWith('/ai ') || t.startsWith('ai:')) return true;
    if (/[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(t)) return true;
    if (/^(help|what|how|why|who|when|where|list|show|find|check|explain|diagnose|排查|分析|查看|怎么|为什么|如何)\b/i.test(t)) {
      return true;
    }
    if (/\s/.test(t) && !/^[a-z0-9_./\\-]+$/i.test(t)) return true;
    return false;
  }

  function normalizeAiQuery(line) {
    let t = (line || '').trim();
    if (t.startsWith('!')) t = t.slice(1).trim();
    if (t.startsWith('?')) t = t.slice(1).trim();
    if (t.startsWith('/ai ')) t = t.slice(4).trim();
    if (t.toLowerCase().startsWith('ai:')) t = t.slice(3).trim();
    return t;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function write(term, text) {
    if (term && text) term.write(text);
  }

  function writeln(term, text) {
    if (term) term.writeln(text);
  }

  function shellHint(term, text) {
    if (!term) return;
    writeln(term, `\x1b[90m${text}\x1b[0m`);
  }

  function prepareMessages(session, userText) {
    const base = Array.isArray(session?.messages) ? session.messages.slice(-40) : [];
    const prepared = typeof deps.prepareMessagesForApi === 'function'
      ? deps.prepareMessagesForApi(base)
      : base;
    return [...prepared, { role: 'user', content: userText }];
  }

  async function cancel() {
    if (!activeJobId || !deps.api) return;
    const jobId = activeJobId;
    try {
      await deps.api('DELETE', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}`);
    } catch {}
  }

  async function pollJob(jobId, ui) {
    let since = 0;
    while (running && activeJobId === jobId) {
      const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=${since}`);
      if (!data?.ok) {
        ui?.setError(data?.error || '请求失败');
        break;
      }

      for (const ev of data.events || []) {
        const seq = Number(ev._seq || 0);
        if (seq > since) since = seq;

        if (ev.type === 'reasoning') {
          if (ui?.thinkingEl) {
            ui.thinkingEl.hidden = false;
            if (ui.thinkingBody) ui.thinkingBody.textContent += ev.delta || '';
          }
        } else if (ev.type === 'content') {
          if (ui?.contentEl) {
            ui.contentEl.hidden = false;
            ui.contentEl.textContent += ev.delta || '';
          }
        } else if (ev.type === 'tool_call') {
          if (ui?.toolsEl) {
            const row = document.createElement('div');
            row.className = 'terminal-ai-tool';
            row.textContent = `▸ ${ev.name || 'tool'}`;
            ui.toolsEl.appendChild(row);
          }
        } else if (ev.type === 'tool_result') {
          if (ui?.toolsEl?.lastElementChild) {
            const ok = ev.result?.ok !== false && !ev.result?.error;
            ui.toolsEl.lastElementChild.classList.add(ok ? 'ok' : 'err');
            ui.toolsEl.lastElementChild.textContent += ok ? ' ✓' : ' ✗';
          }
        } else if (ev.type === 'error') {
          ui?.setError(ev.error || 'error');
        }
        scrollFeed();
      }

      if (['done', 'error', 'cancelled'].includes(data.status)) {
        if (data.status === 'error') {
          ui?.setError(data.error || '任务失败');
        } else if (data.status === 'cancelled') {
          ui?.finish('已取消');
        } else {
          ui?.finish();
        }
        break;
      }
      await sleep(350);
    }
  }

  async function runQuery(rawLine, term) {
    const query = normalizeAiQuery(rawLine);
    if (!query || running) return;
    if (!deps.api || !deps.SessionStore) {
      shellHint(term, '[op助手] AI 未初始化');
      return;
    }

    const ui = createTurn(query);
    if (!ui) {
      shellHint(term, '[op助手] AI 面板未就绪');
      return;
    }

    running = true;
    activeJobId = null;
    deps.onAiActivity?.(true);
    deps.SessionStore.ensureSessionOnSend?.(query);
    const session = deps.SessionStore.getActive?.();
    const sessionId = session?.id;
    if (!sessionId) {
      ui.setError('无活动会话');
      running = false;
      deps.onAiActivity?.(false);
      return;
    }

    shellHint(term, '↑ AI 回复见上方面板');

    try {
      const messages = prepareMessages(session, query);
      const idempotencyKey = `terminal-${sessionId}-${Date.now()}`;
      const queueExtras = (typeof CommandQueue !== 'undefined' && deps.getState?.()?.driving)
        ? CommandQueue.payloadExtras(true)
        : {};

      const { data: startData } = await deps.api('POST', '/api/ai/chat/jobs', {
        sessionId,
        idempotencyKey,
        messages,
        tools: true,
        mode: deps.chatMode || 'unlimited',
        maxToolRounds: 'infinite',
        source: 'terminal',
        ...queueExtras,
      });

      if (!startData?.ok) {
        ui.setError(startData?.error || '无法启动 AI 任务');
        return;
      }
      if (startData.queued || startData.action === 'collected') {
        const pos = startData.queuePosition || startData.collectBatch || '?';
        ui.finish(`已加入行驶队列（${pos}）`);
        return;
      }
      if (!startData.jobId) {
        ui.setError('无法启动 AI 任务');
        return;
      }

      activeJobId = startData.jobId;
      deps.SessionStore.setActiveJobId?.(sessionId, startData.jobId);
      await pollJob(startData.jobId, ui);
      deps.syncSessionsToDevice?.().catch(() => {});
    } catch (e) {
      ui.setError(e?.message || String(e));
    } finally {
      running = false;
      activeJobId = null;
      deps.onAiActivity?.(false);
    }
  }

  function resetLineBuffer() {
    lineBuffer = '';
  }

  function processInput(data, ws, term, { aiOnly = false } = {}) {
    let i = 0;
    while (i < data.length) {
      const ch = data[i];

      if (ch === '\x1b') {
        const chunk = data.slice(i);
        if (!aiOnly && ws?.readyState === WebSocket.OPEN && !deps.ptyMuted?.()) {
          ws.send(chunk);
        }
        return;
      }

      if (ch === '\r' || ch === '\n') {
        const line = lineBuffer;
        lineBuffer = '';
        if (aiOnly) term.write('\r\n');
        if (shouldRouteToAi(line)) {
          if (!aiOnly && ws?.readyState === WebSocket.OPEN) {
            ws.send('\x15');
            ws.send('\r');
          }
          runQuery(line, term);
          if (aiOnly) writePrompt(term);
          i += 1;
          continue;
        }
        if (aiOnly) {
          shellHint(term, '（AI 模式：自然语言，或 ! 前缀强制 Shell）');
          writePrompt(term);
        } else if (ws?.readyState === WebSocket.OPEN && !deps.ptyMuted?.()) {
          ws.send(ch);
        }
        i += 1;
        continue;
      }

      if (ch === '\x7f' || ch === '\b') {
        lineBuffer = lineBuffer.slice(0, -1);
        if (aiOnly) term.write('\b \b');
      } else if (ch === '\x03') {
        lineBuffer = '';
        if (running) cancel();
        if (aiOnly) {
          term.write('^C\r\n');
          writePrompt(term);
        } else if (ws?.readyState === WebSocket.OPEN && !deps.ptyMuted?.()) {
          ws.send(ch);
        }
        i += 1;
        continue;
      } else if (ch >= ' ' || ch === '\t') {
        lineBuffer += ch;
        if (aiOnly) term.write(ch);
      }

      if (!aiOnly && ws?.readyState === WebSocket.OPEN && !deps.ptyMuted?.()) {
        ws.send(ch);
      }
      i += 1;
    }
  }

  function writePrompt(term) {
    write(term, '\x1b[32mop助手>\x1b[0m ');
  }

  function attach(term, ws, opts = {}) {
    if (!term) return;
    resetLineBuffer();
    term.onData((data) => {
      processInput(data, ws, term, opts);
    });
  }

  function printHelp(term, { aiOnly = false } = {}) {
    writeln(term, '\x1b[33m终端 AI\x1b[0m：自然语言 / \x1b[36m?\x1b[0m / \x1b[36m/ai\x1b[0m → 上方 AI 面板；\x1b[36m!\x1b[0m 强制 Shell。');
    if (aiOnly) writePrompt(term);
  }

  return {
    init,
    attach,
    runQuery,
    cancel,
    isRunning,
    shouldRouteToAi,
    printHelp,
    resetLineBuffer,
    clearFeed,
  };
})();
