/**
 * Platform settings — workspace, MCP, learned skills, session search, debug toggles.
 */
const PlatformPanel = (() => {
  let api = null;

  function init(deps = {}) {
    api = deps.api || (typeof WebApi !== 'undefined' ? WebApi.api : null);
    bind();
    loadDebugToggles();
  }

  function loadDebugToggles() {
    const prefs = (typeof LocalPrefs !== 'undefined' && LocalPrefs.getChatDebugPrefs)
      ? LocalPrefs.getChatDebugPrefs()
      : { verbose: false, trace: false };
    const verbose = document.getElementById('chatVerboseToggle');
    const trace = document.getElementById('chatTraceToggle');
    if (verbose) verbose.checked = !!prefs.verbose;
    if (trace) trace.checked = !!prefs.trace;
  }

  function saveDebugToggles() {
    if (typeof LocalPrefs === 'undefined' || !LocalPrefs.setChatDebugPrefs) return;
    LocalPrefs.setChatDebugPrefs({
      verbose: !!document.getElementById('chatVerboseToggle')?.checked,
      trace: !!document.getElementById('chatTraceToggle')?.checked,
    });
  }

  async function loadWorkspace() {
    const key = document.getElementById('platformWorkspaceKey')?.value || 'user';
    const { data } = await api('GET', `/api/ai/workspace?key=${encodeURIComponent(key)}`);
    const editor = document.getElementById('platformWorkspaceEditor');
    if (editor && data?.ok) editor.value = data.content || '';
  }

  async function saveWorkspace() {
    const key = document.getElementById('platformWorkspaceKey')?.value || 'user';
    const content = document.getElementById('platformWorkspaceEditor')?.value || '';
    await api('POST', '/api/ai/workspace', { key, content });
  }

  async function refreshMcp() {
    const box = document.getElementById('platformMcpList');
    if (!box) return;
    const { data } = await api('GET', '/api/ai/mcp');
    box.innerHTML = '';
    for (const s of (data?.servers || [])) {
      const row = document.createElement('div');
      row.className = 'platform-list-item';
      row.textContent = `${s.id} · ${s.command || ''} · tools=${s.toolCount || 0}`;
      box.appendChild(row);
    }
  }

  async function addMcp() {
    const id = document.getElementById('platformMcpId')?.value?.trim();
    const command = document.getElementById('platformMcpCmd')?.value?.trim();
    if (!id || !command) return;
    await api('POST', '/api/ai/mcp', { id, command, enabled: true });
    await refreshMcp();
  }

  async function refreshLearned() {
    const box = document.getElementById('platformLearnedList');
    if (!box) return;
    const { data } = await api('GET', '/api/ai/learned-skills');
    box.innerHTML = '';
    for (const s of (data?.skills || [])) {
      const row = document.createElement('div');
      row.className = 'platform-list-item';
      const title = document.createElement('span');
      title.textContent = `${s.title || s.id} [${s.status}]`;
      row.appendChild(title);
      if (s.status === 'pending') {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn small';
        btn.textContent = '批准';
        btn.addEventListener('click', async () => {
          await api('POST', '/api/ai/learned-skills', { skill_id: s.id });
          refreshLearned();
        });
        row.appendChild(btn);
      }
      box.appendChild(row);
    }
  }

  async function searchSessions() {
    const q = document.getElementById('platformSessionQuery')?.value?.trim();
    const box = document.getElementById('platformSessionHits');
    if (!box || !q) return;
    const { data } = await api('GET', `/api/ai/sessions/search?q=${encodeURIComponent(q)}`);
    box.innerHTML = '';
    for (const hit of (data?.hits || [])) {
      const row = document.createElement('div');
      row.className = 'platform-list-item';
      row.textContent = `${hit.sessionTitle || hit.sessionId}: ${hit.snippet || ''}`;
      box.appendChild(row);
    }
  }

  function bind() {
    document.getElementById('platformWorkspaceLoad')?.addEventListener('click', () => loadWorkspace().catch(console.error));
    document.getElementById('platformWorkspaceSave')?.addEventListener('click', () => saveWorkspace().catch(console.error));
    document.getElementById('platformWorkspaceKey')?.addEventListener('change', () => loadWorkspace().catch(console.error));
    document.getElementById('platformMcpAdd')?.addEventListener('click', () => addMcp().catch(console.error));
    document.getElementById('platformSessionSearch')?.addEventListener('click', () => searchSessions().catch(console.error));
    document.getElementById('chatVerboseToggle')?.addEventListener('change', saveDebugToggles);
    document.getElementById('chatTraceToggle')?.addEventListener('change', saveDebugToggles);
    document.getElementById('schedNlBtn')?.addEventListener('click', async () => {
      const text = document.getElementById('schedNlInput')?.value?.trim();
      if (!text || !api) return;
      await api('POST', '/api/ai/scheduler', { nl: text });
      document.getElementById('schedNlInput').value = '';
      if (typeof loadSchedulerTasks === 'function') loadSchedulerTasks();
    });
  }

  function onSettingsOpen(tab) {
    if (tab !== 'platform') return;
    loadWorkspace().catch(() => {});
    refreshMcp().catch(() => {});
    refreshLearned().catch(() => {});
    loadDebugToggles();
  }

  return { init, onSettingsOpen, getChatDebugPrefs: () => (
    (typeof LocalPrefs !== 'undefined' && LocalPrefs.getChatDebugPrefs)
      ? LocalPrefs.getChatDebugPrefs()
      : { verbose: false, trace: false }
  ) };
})();
