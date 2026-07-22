/**
 * Web terminal — xterm.js + PTY WebSocket (Hermes-inspired).
 */
const TerminalPanel = (() => {
  let panel = null;
  let term = null;
  let ws = null;
  let fitAddon = null;
  let open = false;

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}/api/ai/terminal/ws`;
  }

  function ensureDom() {
    panel = document.getElementById('terminalPanel');
    const closeBtn = document.getElementById('terminalCloseBtn');
    const toggleBtn = document.getElementById('terminalToggleBtn');
    const backdrop = document.getElementById('terminalBackdrop');
    if (closeBtn && !closeBtn.dataset.bound) {
      closeBtn.dataset.bound = '1';
      closeBtn.addEventListener('click', () => setOpen(false));
    }
    if (backdrop && !backdrop.dataset.bound) {
      backdrop.dataset.bound = '1';
      backdrop.addEventListener('click', () => setOpen(false));
    }
    if (toggleBtn && !toggleBtn.dataset.bound) {
      toggleBtn.dataset.bound = '1';
      toggleBtn.addEventListener('click', () => setOpen(!open));
    }
  }

  function setOpen(v) {
    open = !!v;
    ensureDom();
    if (panel) {
      panel.classList.toggle('open', open);
      panel.setAttribute('aria-hidden', open ? 'false' : 'true');
    }
    document.getElementById('terminalBackdrop')?.classList.toggle('hidden', !open);
    if (open) {
      connect();
      if (typeof TerminalSidecar !== 'undefined') TerminalSidecar.connect();
      setTimeout(() => fitTerminal(), 80);
    } else {
      disconnect();
      if (typeof TerminalSidecar !== 'undefined') TerminalSidecar.disconnect();
    }
  }

  function fitTerminal() {
    if (fitAddon && term) {
      try { fitAddon.fit(); } catch {}
      if (ws?.readyState === WebSocket.OPEN && term.cols && term.rows) {
        ws.send(`\x1b[RESIZE:${term.cols};${term.rows}]`);
      }
    }
  }

  function connect() {
    if (typeof Terminal === 'undefined') {
      console.warn('xterm.js not loaded');
      return;
    }
    const host = document.getElementById('terminalHost');
    if (!host) return;
    if (!term) {
      term = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: 'Consolas, "Cascadia Mono", "SF Mono", Menlo, monospace',
        theme: { background: '#0d1117', foreground: '#e6edf3' },
      });
      if (typeof FitAddon !== 'undefined') {
        fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
      }
      term.open(host);
      term.writeln('\x1b[33mop助手 Web 终端\x1b[0m — AGNOS/Linux PTY');
      term.writeln('连接中…\r\n');
      window.addEventListener('resize', () => fitTerminal());
    }
    disconnect();
    try {
      ws = new WebSocket(wsUrl());
      ws.binaryType = 'arraybuffer';
    } catch (e) {
      term.writeln(`\x1b[31mWebSocket 失败: ${e.message}\x1b[0m`);
      return;
    }
    ws.onopen = () => {
      term.writeln('\x1b[32m已连接\x1b[0m');
      fitTerminal();
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') term.write(ev.data);
      else term.write(new Uint8Array(ev.data));
    };
    ws.onclose = () => term.writeln('\r\n\x1b[33m连接已关闭\x1b[0m');
    ws.onerror = () => term.writeln('\r\n\x1b[31m终端错误\x1b[0m');
    term.onData((data) => {
      if (ws?.readyState === WebSocket.OPEN) ws.send(data);
    });
  }

  function disconnect() {
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
  }

  return { setOpen, connect, disconnect };
})();
