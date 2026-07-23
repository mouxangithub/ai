/**
 * Builtin agents UI — settings, stream events, office usage (extracted from ai.js).
 */
const AgentsPanel = (() => {
  let deps = {};
  let builtinAgents = [];
  let currentActiveAgentId = 'op';
  let orchestrationActive = false;

  function init(options = {}) {
    deps = options;
  }

  function getCurrentAgentId() {
    return currentActiveAgentId;
  }

  function setOrchestrationActive(active) {
    orchestrationActive = !!active;
  }

  function applyBuiltinAgents(data) {
    if (Array.isArray(data?.agents)) {
      builtinAgents = data.agents;
      if (typeof OfficePanel !== 'undefined') OfficePanel.setAgents(builtinAgents);
    }
    if (data?.office && typeof OfficePanel !== 'undefined') {
      OfficePanel.applyOffice(data.office);
    }
  }

  async function refreshOfficeUsage() {
    try {
      const { data } = await deps.api('GET', '/api/ai/usage');
      if (data.ok && data.usage && typeof OfficePanel !== 'undefined') {
        OfficePanel.setUsageTokens(data.usage.total_tokens || 0);
      }
    } catch (_) { /* ignore */ }
  }

  function updateActiveAgentBadge(agentId, route) {
    const el = deps.els?.activeAgentBadge;
    if (!el) return;
    const meta = typeof OfficePanel !== 'undefined' ? OfficePanel.agentMeta(agentId) : { icon: '🤖', name: agentId };
    if (!agentId || agentId === 'op') {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.classList.remove('hidden');
    el.textContent = `${meta.icon} ${meta.name}`;
    el.title = route?.agentDescription || meta.description || '';
  }

  function appendOrchestrationBanner(data) {
    const plan = data.plan || [];
    const names = plan.map((p) => {
      const aid = p.agent_id || p.agentId;
      const meta = typeof OfficePanel !== 'undefined' ? OfficePanel.agentMeta(aid) : { icon: '🤖', name: aid };
      return `${meta.icon} ${meta.name || aid}`;
    }).join(' → ');
    const escapeHtml = deps.escapeHtml || ((s) => String(s || ''));
    deps.els?.messages?.querySelector('.orchestration-banner')?.remove();
    const div = document.createElement('div');
    div.className = 'orchestration-banner';
    div.innerHTML = `<span>🧭</span><span><strong>多专员编排</strong> · ${escapeHtml(names)}</span>`;
    deps.els?.messages?.appendChild(div);
    deps.scrollToBottom?.();
  }

  function appendAgentSummaryBlock(data) {
    const aid = data.agentId || data.agent_id || 'op';
    const meta = typeof OfficePanel !== 'undefined' ? OfficePanel.agentMeta(aid) : {};
    const escapeHtml = deps.escapeHtml || ((s) => String(s || ''));
    const div = document.createElement('div');
    div.className = 'agent-summary-block';
    const body = (data.content || '').trim() || '（已通过工具完成子任务）';
    div.innerHTML = `
      <div class="agent-summary-head">${meta.icon || '🤖'} ${escapeHtml(meta.name || data.agentName || aid)}</div>
      <div class="agent-summary-body">${escapeHtml(body)}</div>
    `;
    deps.els?.messages?.appendChild(div);
    deps.scrollToBottom?.();
  }

  function appendOrchestrationSynthesisBanner() {
    deps.els?.messages?.querySelector('.orchestration-synthesis-banner')?.remove();
    const div = document.createElement('div');
    div.className = 'orchestration-synthesis-banner';
    div.innerHTML = '<span>🎯</span><span><strong>OP 主调度</strong> 正在汇总结论…</span>';
    deps.els?.messages?.appendChild(div);
    deps.scrollToBottom?.();
  }

  function appendAgentHandoffBanner(route) {
    if (!route || (route.agent_id === 'op' && route.reason === 'default')) return;
    const aid = route.agent_id || route.agentId || 'op';
    if (aid === 'op') return;
    const escapeHtml = deps.escapeHtml || ((s) => String(s || ''));
    deps.els?.messages?.querySelector('.agent-handoff-banner')?.remove();
    const meta = typeof OfficePanel !== 'undefined' ? OfficePanel.agentMeta(aid) : {};
    const div = document.createElement('div');
    div.className = 'agent-handoff-banner';
    div.innerHTML = `<span>${meta.icon || '🤖'}</span><span><strong>${escapeHtml(meta.name || route.agentName || aid)}</strong> 已接手${route.workflow_id ? ` · ${escapeHtml(route.workflow_id)}` : ''}</span>`;
    deps.els?.messages?.appendChild(div);
    deps.scrollToBottom?.();
  }

  function handleStreamEvent(data) {
    if (!data?.type) return;
    if (data.type === 'orchestration_start') {
      orchestrationActive = true;
      appendOrchestrationBanner(data);
      if (data.office && typeof OfficePanel !== 'undefined') {
        OfficePanel.applyOffice(data.office);
      }
    }
    if (data.type === 'agent_summary') appendAgentSummaryBlock(data);
    if (data.type === 'orchestration_synthesis') appendOrchestrationSynthesisBanner();
    if (data.type === 'agent_handoff') {
      currentActiveAgentId = data.agent_id || data.agentId || 'op';
      updateActiveAgentBadge(currentActiveAgentId, data);
      appendAgentHandoffBanner(data);
      if (data.office && typeof OfficePanel !== 'undefined') OfficePanel.applyOffice(data.office);
    }
    if (data.type === 'agent_office' && data.office) {
      if (typeof OfficePanel !== 'undefined') OfficePanel.applyOffice(data.office);
    }
    if (data.type === 'agent_status' && data.office) {
      if (typeof OfficePanel !== 'undefined') OfficePanel.applyOffice(data.office);
    }
    if (data.type === 'agent_done') {
      if (data.office && typeof OfficePanel !== 'undefined') OfficePanel.applyOffice(data.office);
      if (!orchestrationActive) {
        currentActiveAgentId = 'op';
        updateActiveAgentBadge('op');
      }
    }
    if (data.type === 'done') {
      orchestrationActive = false;
      currentActiveAgentId = 'op';
      updateActiveAgentBadge('op');
    }
  }

  return {
    init,
    applyBuiltinAgents,
    refreshOfficeUsage,
    handleStreamEvent,
    getCurrentAgentId,
    setOrchestrationActive,
    updateActiveAgentBadge,
  };
})();
