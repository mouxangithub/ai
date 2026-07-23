/**
 * Canvas artifacts — embedded in 设置 → 开发.
 */
const CanvasPanel = (() => {
  let listEl = null;
  let filterEl = null;
  const bySession = new Map();
  let activeFilter = 'all';

  function ensureDom() {
    listEl = document.getElementById('canvasList');
    filterEl = document.getElementById('canvasFilter');
    if (filterEl && !filterEl.dataset.bound) {
      filterEl.dataset.bound = '1';
      filterEl.addEventListener('change', () => {
        activeFilter = filterEl.value || 'all';
        render();
      });
    }
  }

  function addArtifact(sessionId, artifact) {
    if (!artifact) return;
    const sid = sessionId || '__global__';
    const items = bySession.get(sid) || [];
    items.unshift(artifact);
    bySession.set(sid, items.slice(0, 30));
    updateBadge(items.length);
    render(sessionId);
  }

  function updateBadge(n) {
    const count = Number(n) || 0;
    const badge = document.getElementById('devCanvasCount');
    if (badge) badge.textContent = String(count);
  }

  function renderBody(artifact) {
    const payload = artifact.payload || {};
    if (payload.markdown && typeof renderMarkdown === 'function') {
      const div = document.createElement('div');
      div.className = 'canvas-md';
      renderMarkdown(div, String(payload.markdown));
      return div.outerHTML;
    }
    if (payload.html) {
      return `<div class="canvas-html sandbox">${String(payload.html).slice(0, 12000)}</div>`;
    }
    if (payload.report) {
      const pre = escapeHtml(JSON.stringify(payload.report, null, 2).slice(0, 8000));
      return `<pre class="canvas-pre">${pre}</pre>`;
    }
    if (payload.chart) {
      return `<pre class="canvas-pre canvas-chart">${escapeHtml(JSON.stringify(payload.chart, null, 2).slice(0, 6000))}</pre>`;
    }
    return `<pre class="canvas-pre">${escapeHtml(JSON.stringify(payload, null, 2).slice(0, 4000))}</pre>`;
  }

  function render(sessionId) {
    ensureDom();
    if (!listEl) return;
    const sid = sessionId || (typeof SessionStore !== 'undefined' ? SessionStore.activeId : '');
    let items = bySession.get(sid) || [];
    if (activeFilter !== 'all') {
      items = items.filter((a) => (a.kind || '') === activeFilter);
    }
    if (!items.length) {
      listEl.innerHTML = '<p class="canvas-empty">暂无可视化输出</p>';
      updateBadge((bySession.get(sid) || []).length);
      return;
    }
    listEl.innerHTML = items.map((a) => {
      const kind = a.kind || 'report';
      const title = a.title || a.sourceTool || kind;
      const ts = a.createdAt ? new Date(a.createdAt * 1000).toLocaleString() : '';
      return `<article class="canvas-item" data-id="${a.id || ''}">
        <header>
          <span class="canvas-kind">${escapeHtml(kind)}</span>
          <strong>${escapeHtml(title)}</strong>
          <time>${escapeHtml(ts)}</time>
          <button type="button" class="btn small ghost canvas-export" data-id="${a.id || ''}">导出</button>
        </header>
        ${renderBody(a)}
      </article>`;
    }).join('');
    listEl.querySelectorAll('.canvas-export').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const art = items.find((x) => x.id === id);
        if (!art) return;
        const blob = new Blob([JSON.stringify(art, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${art.kind || 'artifact'}_${id}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
      });
    });
    updateBadge((bySession.get(sid) || []).length);
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadSession(sessionId) {
    if (!sessionId || typeof api !== 'function') return;
    const { data } = await api('GET', `/api/ai/canvas?sessionId=${encodeURIComponent(sessionId)}&limit=30`);
    if (!data?.ok) return;
    bySession.set(sessionId, data.artifacts || []);
    updateBadge((data.artifacts || []).length);
    render(sessionId);
  }

  function handleWs(payload) {
    addArtifact(payload.sessionId, payload.artifact);
  }

  return { addArtifact, render, loadSession, handleWs };
})();
