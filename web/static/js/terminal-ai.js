/**
 * Hermes-style terminal AI — natural language routes to op助手.
 * Replies stream inline in xterm (PTY muted during AI to avoid layout clash).
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

  function sanitizeText(s) {
    return String(s || '')
      .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
      .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '');
  }

  class TermInlineWriter {
    constructor(term) {
      this.term = term;
      this.buf = { content: '', reasoning: '' };
    }

    cols() {
      return Math.max(40, (this.term?.cols || 80) - 2);
    }

    scrollBottom() {
      try {
        this.term?.scrollToBottom?.();
      } catch {}
    }

    wrapLines(text) {
      const max = this.cols();
      const out = [];
      let remaining = String(text || '').replace(/\r/g, '');
      while (remaining.length > 0) {
        if (remaining.length <= max) {
          out.push(remaining);
          break;
        }
        let breakAt = max;
        const slice = remaining.slice(0, max + 1);
        const lastSpace = slice.lastIndexOf(' ');
        if (lastSpace > max * 0.4) breakAt = lastSpace;
        out.push(remaining.slice(0, breakAt).trimEnd());
        remaining = remaining.slice(breakAt).trimStart();
      }
      return out.length ? out : [''];
    }

    writelnStyled(text, style = '') {
      if (!this.term || text === '') return;
      for (const line of this.wrapLines(text)) {
        this.term.writeln(style ? `${style}${line}\x1b[0m` : line);
      }
      this.scrollBottom();
    }

    flushBuf(key) {
      const buf = this.buf[key];
      const nl = buf.indexOf('\n');
      if (nl === -1) return;
      const line = buf.slice(0, nl);
      this.buf[key] = buf.slice(nl + 1);
      if (key === 'reasoning') {
        this.writelnStyled(`[思考] ${line}`, '\x1b[90m');
      } else {
        this.writelnStyled(line);
      }
      if (this.buf[key]) this.flushBuf(key);
    }

    append(delta, type) {
      const key = type === 'reasoning' ? 'reasoning' : 'content';
      this.buf[key] += sanitizeText(delta);
      this.flushBuf(key);
    }

    flushAll() {
      for (const key of ['reasoning', 'content']) {
        const text = this.buf[key].trim();
        if (!text) continue;
        if (key === 'reasoning') {
          this.writelnStyled(`[思考] ${text}`, '\x1b[90m');
        } else {
          this.writelnStyled(text);
        }
        this.buf[key] = '';
      }
    }

    toolCall(name) {
      if (!this.term) return;
      this.term.writeln(`\x1b[33m  ▸ ${name || 'tool'}\x1b[0m`);
      this.scrollBottom();
    }

    toolResult(ok) {
      if (!this.term) return;
      this.term.writeln(`\x1b[${ok ? '32' : '31'}m    ${ok ? '✓' : '✗'}\x1b[0m`);
      this.scrollBottom();
    }

    error(msg) {
      this.writelnStyled(`[错误] ${msg}`, '\x1b[31m');
    }

    done(statusText) {
      if (statusText) this.writelnStyled(`[op助手] ${statusText}`, '\x1b[90m');
    }
  }

  function shouldRouteToAi(line) {
    const t = (line || '').trim();
    if (!t) return false;
    if (t.startsWith('!')) return false;
    if (t === '/help' || t === 'help' || t === '?') return true;
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
    if (t === '/help' || t === 'help' || t === '?') return '';
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

  async function pollJob(jobId, writer) {
    let since = 0;
    while (running && activeJobId === jobId) {
      const { data } = await deps.api('GET', `/api/ai/chat/jobs/${encodeURIComponent(jobId)}?since=${since}`);
      if (!data?.ok) {
        writer?.error(data?.error || '请求失败');
        break;
      }

      for (const ev of data.events || []) {
        const seq = Number(ev._seq || 0);
        if (seq > since) since = seq;

        if (ev.type === 'reasoning') {
          writer?.append(ev.delta || '', 'reasoning');
        } else if (ev.type === 'content') {
          writer?.append(ev.delta || '', 'content');
        } else if (ev.type === 'tool_call') {
          writer?.flushAll();
          writer?.toolCall(ev.name || 'tool');
        } else if (ev.type === 'tool_result') {
          const ok = ev.result?.ok !== false && !ev.result?.error;
          writer?.toolResult(ok);
        } else if (ev.type === 'error') {
          writer?.flushAll();
          writer?.error(ev.error || 'error');
        }
      }

      if (['done', 'error', 'cancelled'].includes(data.status)) {
        writer?.flushAll();
        if (data.status === 'error') {
          writer?.error(data.error || '任务失败');
        } else if (data.status === 'cancelled') {
          writer?.done('已取消');
        }
        break;
      }
      await sleep(350);
    }
  }

  async function runQuery(rawLine, term, { aiOnly = false } = {}) {
    const query = normalizeAiQuery(rawLine);
    if (rawLine.trim() === '/help' || rawLine.trim() === 'help' || rawLine.trim() === '?') {
      printHelp(term, { aiOnly });
      return;
    }
    if (!query || running) return;
    if (!deps.api || !deps.SessionStore) {
      shellHint(term, '[op助手] AI 未初始化');
      return;
    }

    const writer = new TermInlineWriter(term);
    running = true;
    activeJobId = null;
    deps.onAiActivity?.(true);
    deps.SessionStore.ensureSessionOnSend?.(query);
    const session = deps.SessionStore.getActive?.();
    const sessionId = session?.id;
    if (!sessionId) {
      writer.error('无活动会话');
      running = false;
      deps.onAiActivity?.(false);
      if (aiOnly) writePrompt(term);
      return;
    }

    writeln(term, `\x1b[36m[你]\x1b[0m ${query}`);
    shellHint(term, '[op助手] 处理中…');

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
        writer.error(startData?.error || '无法启动 AI 任务');
        return;
      }
      if (startData.queued || startData.action === 'collected') {
        const pos = startData.queuePosition || startData.collectBatch || '?';
        writer.done(`已加入行驶队列（${pos}）`);
        return;
      }
      if (!startData.jobId) {
        writer.error('无法启动 AI 任务');
        return;
      }

      activeJobId = startData.jobId;
      deps.SessionStore.setActiveJobId?.(sessionId, startData.jobId);
      await pollJob(startData.jobId, writer);
      deps.syncSessionsToDevice?.().catch(() => {});
      writeln(term, '');
    } catch (e) {
      writer.error(e?.message || String(e));
    } finally {
      running = false;
      activeJobId = null;
      deps.onAiActivity?.(false);
      if (aiOnly) writePrompt(term);
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
          runQuery(line, term, { aiOnly });
        } else if (aiOnly) {
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
    writeln(term, '\x1b[33m终端 AI\x1b[0m：自然语言 / \x1b[36m?\x1b[0m / \x1b[36m/ai\x1b[0m 直接在此对话；\x1b[36m!\x1b[0m 强制 Shell；\x1b[36m/help\x1b[0m 显示本帮助。');
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
