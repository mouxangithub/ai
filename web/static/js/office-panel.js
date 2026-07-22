/**
 * OP 办公室 — 内置专员可视化（马威斯风格简化版）
 */
const OfficePanel = (() => {
  let root = null;
  let gridEl = null;
  let tasksEl = null;
  let statsEl = null;
  let backdrop = null;
  let toggleBtn = null;
  let agentsById = new Map();
  let officeState = null;
  let usageTokens = 0;
  let onOpenCallback = null;
  let open = false;

  const STATUS_LABEL = {
    idle: '空闲',
    assigned: '已派活',
    working: '执行中',
    waiting: '待确认',
  };

  function agentMeta(id) {
    const a = agentsById.get(id);
    return a || { id: id || 'op', name: id || 'op', icon: '🤖' };
  }

  function setAgents(list) {
    agentsById = new Map();
    for (const a of list || []) {
      if (a?.id) agentsById.set(a.id, a);
    }
    renderGrid();
  }

  function applyOffice(data) {
    officeState = data || null;
    renderGrid();
    renderTasks();
    renderStats();
  }

  function setUsageTokens(total) {
    usageTokens = Number(total) || 0;
    renderStats();
  }

  function formatTokens(n) {
    const v = Number(n) || 0;
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(v);
  }

  function renderStats() {
    if (!statsEl) return;
    const active = officeState?.activeCount ?? 0;
    const tasks = officeState?.tasks?.length ?? 0;
    statsEl.innerHTML = `
      <div class="office-stat"><span>进行中</span><b>${active}</b></div>
      <div class="office-stat"><span>任务记录</span><b>${tasks}</b></div>
      <div class="office-stat"><span>累计 Token</span><b>${formatTokens(usageTokens)}</b></div>
    `;
  }

  function renderGrid() {
    if (!gridEl) return;
    const statusMap = new Map();
    for (const a of officeState?.agents || []) {
      statusMap.set(a.id, a);
    }
    const list = [...agentsById.values()].sort((a, b) => {
      const da = a.desk || {};
      const db = b.desk || {};
      return (da.row - db.row) || (da.col - db.col);
    });
    gridEl.innerHTML = list.map((agent) => {
      const live = statusMap.get(agent.id) || {};
      const status = live.status || 'idle';
      const tool = live.tool ? ` · ${live.tool}` : '';
      const label = STATUS_LABEL[status] || status;
      const active = status !== 'idle';
      return `
        <div class="office-desk ${active ? 'is-active' : ''} status-${status}" data-agent-id="${agent.id}">
          <div class="office-desk-avatar">${agent.icon || '🤖'}</div>
          <div class="office-desk-name">${escapeOffice(agent.name || agent.id)}</div>
          <div class="office-desk-status"><span class="office-dot"></span>${label}${escapeOffice(tool)}</div>
        </div>
      `;
    }).join('');
  }

  function renderTasks() {
    if (!tasksEl) return;
    const tasks = [...(officeState?.tasks || [])].reverse().slice(0, 12);
    if (!tasks.length) {
      tasksEl.innerHTML = `<p class="office-tasks-empty">暂无任务动态</p>`;
      return;
    }
    tasksEl.innerHTML = tasks.map((t) => {
      const meta = agentMeta(t.agentId);
      const time = t.at ? new Date(t.at * 1000).toLocaleTimeString() : '';
      return `
        <div class="office-task status-${t.status || 'info'}">
          <div class="office-task-head">
            <span class="office-task-agent">${meta.icon} ${escapeOffice(meta.name)}</span>
            <span class="office-task-time">${time}</span>
          </div>
          <div class="office-task-msg">${escapeOffice(t.message || '')}</div>
        </div>
      `;
    }).join('');
  }

  function escapeOffice(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function show() {
    if (!root) return;
    open = true;
    root.classList.add('open');
    root.setAttribute('aria-hidden', 'false');
    backdrop?.classList.remove('hidden');
    document.body.classList.add('office-open');
    onOpenCallback?.();
  }

  function hide() {
    if (!root) return;
    open = false;
    root.classList.remove('open');
    root.setAttribute('aria-hidden', 'true');
    backdrop?.classList.add('hidden');
    document.body.classList.remove('office-open');
  }

  function toggle() {
    if (open) hide();
    else show();
  }

  function init(opts = {}) {
    root = opts.panel || document.getElementById('officePanel');
    gridEl = opts.grid || document.getElementById('officeGrid');
    tasksEl = opts.tasks || document.getElementById('officeTasks');
    statsEl = opts.stats || document.getElementById('officeStats');
    backdrop = opts.backdrop || document.getElementById('officeBackdrop');
    toggleBtn = opts.toggleBtn || document.getElementById('officeBtn');
    const closeBtn = opts.closeBtn || document.getElementById('officeCloseBtn');

    toggleBtn?.addEventListener('click', toggle);
    closeBtn?.addEventListener('click', hide);
    backdrop?.addEventListener('click', hide);
    onOpenCallback = opts.onOpen || null;
    renderGrid();
    renderTasks();
    renderStats();
  }

  return {
    init,
    setAgents,
    setUsageTokens,
    applyOffice,
    agentMeta,
    show,
    hide,
    toggle,
    isOpen: () => open,
  };
})();
