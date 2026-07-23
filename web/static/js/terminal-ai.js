/**
 * Hermes-style terminal AI — natural language in Web terminal routes to op助手.
 * Shell commands still go to PTY; lines like「你好」or `?` / `/ai` prefixes invoke the agent.
 */
const TerminalAi = (() => {
  let deps = {};
  let running = false;
  let activeJobId = null;
  let lineBuffer = '';

  function init(d = {}) {
    deps = d;
  }

  function isRunning() {
    return running;
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

  async function pollJob(jobId, term) {
    let since = 0;
    let wroteHeader = false;
    while (running && activeJobId === jobId) {
      const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=${since}`);
      if (!data?.ok) {
        writeln(term, `\x1b[31m[op助手] ${data?.error || '请求失败'}\x1b[0m\r\n`);
        break;
      }

      for (const ev of data.events || []) {
        const seq = Number(ev._seq || 0);
        if (seq > since) since = seq;

        if (ev.type === 'reasoning') {
          if (!wroteHeader) {
            writeln(term, '\x1b[90m[思考]\x1b[0m');
            wroteHeader = true;
          }
          write(term, ev.delta || '');
        } else if (ev.type === 'content') {
          if (!wroteHeader) {
            writeln(term, '\x1b[36m[op助手]\x1b[0m');
            wroteHeader = true;
          }
          write(term, ev.delta || '');
        } else if (ev.type === 'tool_call') {
          writeln(term, `\r\n\x1b[33m[工具] ${ev.name || 'tool'}\x1b[0m`);
        } else if (ev.type === 'tool_result') {
          const ok = ev.result?.ok !== false && !ev.result?.error;
          writeln(term, ok ? '\x1b[32m  ✓ 完成\x1b[0m' : '\x1b[31m  ✗ 失败\x1b[0m');
        } else if (ev.type === 'error') {
          writeln(term, `\r\n\x1b[31m${ev.error || 'error'}\x1b[0m`);
        }
      }

      if (['done', 'error', 'cancelled'].includes(data.status)) {
        if (data.status === 'error') {
          writeln(term, `\r\n\x1b[31m${data.error || '任务失败'}\x1b[0m`);
        }
        writeln(term, '');
        break;
      }
      await sleep(350);
    }
  }

  async function runQuery(rawLine, term) {
    const query = normalizeAiQuery(rawLine);
    if (!query || running) return;
    if (!deps.api || !deps.SessionStore) {
      writeln(term, '\x1b[31m[op助手] AI 未初始化\x1b[0m\r\n');
      return;
    }

    running = true;
    activeJobId = null;
    deps.SessionStore.ensureSessionOnSend?.(query);
    const session = deps.SessionStore.getActive?.();
    const sessionId = session?.id;
    if (!sessionId) {
      writeln(term, '\x1b[31m[op助手] 无活动会话\x1b[0m\r\n');
      running = false;
      return;
    }

    writeln(term, `\r\n\x1b[36m[op助手]\x1b[0m ${query}`);
    writeln(term, '\x1b[90m处理中…\x1b[0m');

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
        writeln(term, `\x1b[31m${startData?.error || '无法启动 AI 任务'}\x1b[0m\r\n`);
        return;
      }
      if (startData.queued || startData.action === 'collected') {
        const pos = startData.queuePosition || startData.collectBatch || '?';
        writeln(term, `\x1b[33m已加入行驶队列（${pos}）\x1b[0m\r\n`);
        return;
      }
      if (!startData.jobId) {
        writeln(term, '\x1b[31m无法启动 AI 任务\x1b[0m\r\n');
        return;
      }

      activeJobId = startData.jobId;
      deps.SessionStore.setActiveJobId?.(sessionId, startData.jobId);
      await pollJob(startData.jobId, term);
      deps.syncSessionsToDevice?.().catch(() => {});
    } catch (e) {
      writeln(term, `\x1b[31m${e?.message || e}\x1b[0m\r\n`);
    } finally {
      running = false;
      activeJobId = null;
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
        if (!aiOnly && ws?.readyState === WebSocket.OPEN) ws.send(chunk);
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
          writeln(term, '\x1b[90m（AI 模式：输入自然语言，或 ! 前缀强制 Shell）\x1b[0m');
          writePrompt(term);
        } else if (ws?.readyState === WebSocket.OPEN) {
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
        } else if (ws?.readyState === WebSocket.OPEN) {
          ws.send(ch);
        }
        i += 1;
        continue;
      } else if (ch >= ' ' || ch === '\t') {
        lineBuffer += ch;
        if (aiOnly) term.write(ch);
      }

      if (!aiOnly && ws?.readyState === WebSocket.OPEN) ws.send(ch);
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
    writeln(term, '\x1b[33m终端 AI\x1b[0m：直接输入中文/自然语言，或以 \x1b[36m?\x1b[0m / \x1b[36m/ai\x1b[0m 开头调用 op助手；\x1b[36m!\x1b[0m 前缀强制 Shell。');
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
  };
})();
