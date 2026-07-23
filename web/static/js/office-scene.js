/**
 * OP 办公室 — 等距动态场景（Marvis / Claw3D 风格，零依赖，车载可跑）
 * 专员 idle：打盹、喝咖啡、溜达、健身；派活后走向工位并执行。
 */
const OfficeScene = (() => {
  const ISO_X = 0.8660254; // cos(30°)
  const ISO_Y = 0.5;       // sin(30°)

  const IDLE_BEHAVIORS = ['desk', 'coffee', 'walk', 'stretch', 'nap'];
  const STATUS_LABEL = {
    idle: '空闲',
    assigned: '已派活',
    working: '执行中',
    waiting: '待确认',
  };

  let canvas = null;
  let ctx = null;
  let running = false;
  let rafId = 0;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let officeState = null;
  let characters = new Map();
  let hitTargets = [];
  let selectedId = null;
  let onSelectAgent = null;
  let panX = 0;
  let panY = 0;
  let zoom = 1;
  let drag = null;
  let lastT = 0;
  let reducedMotion = false;
  let drivingPaused = false;
  let lastFrameMs = 0;
  const FPS_CAP = 15;
  const FPS_MS = 1000 / FPS_CAP;

  const ROOM = {
    floorW: 9,
    floorH: 7,
    deskCols: 3,
    deskGapX: 2.1,
    deskGapZ: 2.0,
    deskOriginX: -2.1,
    deskOriginZ: -1.2,
  };

  const POIs = {
    coffee: { x: 3.6, z: 2.4, label: '☕' },
    lounge: { x: -3.8, z: 2.6, label: '🛋' },
    door: { x: 0, z: -3.4, label: '🚪' },
  };

  function hashBehavior(id) {
    let h = 0;
    const s = String(id || '');
    for (let i = 0; i < s.length; i += 1) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return IDLE_BEHAVIORS[Math.abs(h) % IDLE_BEHAVIORS.length];
  }

  function project(wx, wy, wz) {
    const sx = (wx - wz) * ISO_X;
    const sy = (wx + wz) * ISO_Y - wy;
    return {
      x: width / 2 + panX + sx * 42 * zoom,
      y: height * 0.58 + panY + sy * 42 * zoom,
    };
  }

  function deskSlot(index) {
    const col = index % ROOM.deskCols;
    const row = Math.floor(index / ROOM.deskCols);
    return {
      x: ROOM.deskOriginX + col * ROOM.deskGapX,
      z: ROOM.deskOriginZ + row * ROOM.deskGapZ,
      row,
      col,
    };
  }

  function agentDeskPos(agent, index) {
    const desk = agent?.desk || {};
    if (Number.isFinite(desk.col) && Number.isFinite(desk.row)) {
      return {
        x: ROOM.deskOriginX + desk.col * ROOM.deskGapX,
        z: ROOM.deskOriginZ + desk.row * ROOM.deskGapZ,
      };
    }
    const slot = deskSlot(index);
    return { x: slot.x, z: slot.z };
  }

  function ensureCharacter(agent, index) {
    const id = agent.id;
    let ch = characters.get(id);
    const desk = agentDeskPos(agent, index);
    if (!ch) {
      ch = {
        id,
        name: agent.name || id,
        icon: agent.icon || '🤖',
        deskX: desk.x,
        deskZ: desk.z,
        x: desk.x,
        z: desk.z,
        y: 0,
        targetX: desk.x,
        targetZ: desk.z,
        status: 'idle',
        tool: '',
        behavior: hashBehavior(id),
        phase: Math.random() * Math.PI * 2,
        walkT: 0,
        bubble: '',
        bubbleT: 0,
      };
      characters.set(id, ch);
    }
    ch.name = agent.name || id;
    ch.icon = agent.icon || '🤖';
    ch.deskX = desk.x;
    ch.deskZ = desk.z;
    return ch;
  }

  function syncAgents(list) {
    const ids = new Set();
    const sorted = [...(list || [])].sort((a, b) => {
      const da = a.desk || {};
      const db = b.desk || {};
      return (da.row - db.row) || (da.col - db.col) || String(a.id).localeCompare(b.id);
    });
    sorted.forEach((agent, index) => {
      if (!agent?.id) return;
      ids.add(agent.id);
      ensureCharacter(agent, index);
    });
    for (const id of [...characters.keys()]) {
      if (!ids.has(id)) characters.delete(id);
    }
  }

  function applyLiveStatus() {
    const statusMap = new Map();
    for (const a of officeState?.agents || []) {
      statusMap.set(a.id, a);
    }
    for (const ch of characters.values()) {
      const live = statusMap.get(ch.id) || {};
      const next = live.status || 'idle';
      if (next !== ch.status) {
        ch.status = next;
        ch.tool = live.tool || '';
        if (next === 'working') {
          ch.bubble = live.tool ? `🔧 ${live.tool}` : '执行中…';
          ch.bubbleT = 2.5;
          ch.targetX = ch.deskX;
          ch.targetZ = ch.deskZ;
        } else if (next === 'assigned') {
          ch.bubble = '收到任务';
          ch.bubbleT = 2;
          ch.targetX = ch.deskX;
          ch.targetZ = ch.deskZ;
        } else if (next === 'idle') {
          ch.tool = '';
        }
      } else if (live.tool && live.tool !== ch.tool) {
        ch.tool = live.tool;
        if (ch.status === 'working') {
          ch.bubble = `🔧 ${live.tool}`;
          ch.bubbleT = 2.5;
        }
      }
    }
  }

  function pickIdleTarget(ch, t) {
    if (ch.status !== 'idle') return;
    const cycle = Math.floor(t / 8 + ch.phase) % 5;
    switch (ch.behavior) {
      case 'coffee':
        ch.targetX = cycle < 2 ? POIs.coffee.x : ch.deskX;
        ch.targetZ = cycle < 2 ? POIs.coffee.z : ch.deskZ;
        break;
      case 'walk':
        ch.targetX = cycle % 2 ? POIs.lounge.x : ch.deskX;
        ch.targetZ = cycle % 2 ? POIs.lounge.z : ch.deskZ;
        break;
      case 'stretch':
      case 'nap':
        ch.targetX = ch.deskX;
        ch.targetZ = ch.deskZ;
        break;
      default:
        ch.targetX = ch.deskX;
        ch.targetZ = ch.deskZ;
    }
  }

  function updateCharacter(ch, dt, t) {
    if (ch.bubbleT > 0) ch.bubbleT -= dt;

    if (ch.status === 'idle') {
      pickIdleTarget(ch, t);
    }

    const dx = ch.targetX - ch.x;
    const dz = ch.targetZ - ch.z;
    const dist = Math.hypot(dx, dz);
    const speed = ch.status === 'working' ? 0 : 1.15;
    if (dist > 0.04) {
      const step = Math.min(dist, speed * dt);
      ch.x += (dx / dist) * step;
      ch.z += (dz / dist) * step;
      ch.walkT += dt * 9;
    } else {
      ch.walkT = 0;
    }

    if (ch.status === 'working') {
      ch.y = 0.08 + Math.sin(t * 14 + ch.phase) * 0.04;
    } else if (ch.status === 'idle' && ch.behavior === 'nap') {
      ch.y = 0.02 + Math.sin(t * 1.2 + ch.phase) * 0.02;
    } else if (ch.walkT > 0) {
      ch.y = Math.abs(Math.sin(ch.walkT)) * 0.07;
    } else {
      ch.y = Math.sin(t * 2 + ch.phase) * 0.025;
    }
  }

  function drawBackdrop() {
    const g = ctx.createRadialGradient(width / 2, height * 0.15, 20, width / 2, height * 0.35, width * 0.7);
    g.addColorStop(0, 'rgba(78, 205, 196, 0.14)');
    g.addColorStop(0.45, 'rgba(30, 41, 59, 0.35)');
    g.addColorStop(1, 'rgba(8, 12, 20, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, width, height);
  }

  function drawWalls() {
    const backL = project(-ROOM.floorW / 2, 0, -ROOM.floorH / 2);
    const backR = project(ROOM.floorW / 2, 0, -ROOM.floorH / 2);
    const backLTop = project(-ROOM.floorW / 2, 2.8, -ROOM.floorH / 2);
    const backRTop = project(ROOM.floorW / 2, 2.8, -ROOM.floorH / 2);
    const leftB = project(-ROOM.floorW / 2, 0, ROOM.floorH / 2);
    const leftT = project(-ROOM.floorW / 2, 2.8, -ROOM.floorH / 2);

    ctx.beginPath();
    ctx.moveTo(backL.x, backL.y);
    ctx.lineTo(backR.x, backR.y);
    ctx.lineTo(backRTop.x, backRTop.y);
    ctx.lineTo(backLTop.x, backLTop.y);
    ctx.closePath();
    const wallG = ctx.createLinearGradient(0, backLTop.y, 0, backL.y);
    wallG.addColorStop(0, 'rgba(51, 65, 85, 0.55)');
    wallG.addColorStop(1, 'rgba(15, 23, 42, 0.25)');
    ctx.fillStyle = wallG;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(backL.x, backL.y);
    ctx.lineTo(leftB.x, leftB.y);
    ctx.lineTo(leftT.x, leftT.y);
    ctx.lineTo(backLTop.x, backLTop.y);
    ctx.closePath();
    const sideG = ctx.createLinearGradient(backL.x, 0, leftB.x, 0);
    sideG.addColorStop(0, 'rgba(30, 41, 59, 0.45)');
    sideG.addColorStop(1, 'rgba(15, 23, 42, 0.15)');
    ctx.fillStyle = sideG;
    ctx.fill();
  }

  function drawAmbientParticles(t) {
    const n = 18;
    for (let i = 0; i < n; i += 1) {
      const phase = t * 0.35 + i * 1.7;
      const wx = Math.sin(phase) * 3.2;
      const wz = Math.cos(phase * 0.8) * 2.4;
      const wy = 1.2 + Math.sin(phase * 1.3) * 0.6;
      const p = project(wx, wy, wz);
      const alpha = 0.15 + Math.sin(phase * 2) * 0.1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 1.2 * zoom, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(78, 205, 196, ${alpha})`;
      ctx.fill();
    }
  }

  function drawFloor() {
    const corners = [
      project(-ROOM.floorW / 2, 0, -ROOM.floorH / 2),
      project(ROOM.floorW / 2, 0, -ROOM.floorH / 2),
      project(ROOM.floorW / 2, 0, ROOM.floorH / 2),
      project(-ROOM.floorW / 2, 0, ROOM.floorH / 2),
    ];
    ctx.beginPath();
    ctx.moveTo(corners[0].x, corners[0].y);
    corners.slice(1).forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.closePath();
    const g = ctx.createLinearGradient(0, height * 0.2, 0, height);
    g.addColorStop(0, 'rgba(78, 205, 196, 0.12)');
    g.addColorStop(1, 'rgba(12, 18, 28, 0.95)');
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = 'rgba(78, 205, 196, 0.28)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    const center = project(0, 0, 0);
    const spot = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, 120 * zoom);
    spot.addColorStop(0, 'rgba(78, 205, 196, 0.08)');
    spot.addColorStop(1, 'rgba(78, 205, 196, 0)');
    ctx.fillStyle = spot;
    ctx.beginPath();
    ctx.ellipse(center.x, center.y, 120 * zoom, 60 * zoom, 0, 0, Math.PI * 2);
    ctx.fill();

    for (let i = -3; i <= 3; i += 1) {
      const a = project(i * 1.2, 0, -ROOM.floorH / 2);
      const b = project(i * 1.2, 0, ROOM.floorH / 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.04)';
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  }

  function drawDesk(wx, wz) {
    const base = project(wx, 0, wz);
    const top = project(wx, 0.42, wz);
    const legL = project(wx - 0.18, 0, wz + 0.12);
    const legR = project(wx + 0.18, 0, wz - 0.12);
    const w = 36 * zoom;
    const h = 20 * zoom;

    ctx.strokeStyle = 'rgba(51, 65, 85, 0.9)';
    ctx.lineWidth = 2 * zoom;
    ctx.beginPath();
    ctx.moveTo(top.x - w * 0.15, top.y);
    ctx.lineTo(legL.x, legL.y + 4 * zoom);
    ctx.moveTo(top.x + w * 0.15, top.y);
    ctx.lineTo(legR.x, legR.y + 4 * zoom);
    ctx.stroke();

    ctx.fillStyle = 'rgba(0,0,0,0.28)';
    ctx.beginPath();
    ctx.ellipse(base.x, base.y + 5 * zoom, w * 0.58, h * 0.38, 0, 0, Math.PI * 2);
    ctx.fill();

    const deskG = ctx.createLinearGradient(top.x, top.y - h, top.x, top.y + h);
    deskG.addColorStop(0, 'rgba(71, 85, 105, 0.98)');
    deskG.addColorStop(1, 'rgba(30, 41, 59, 0.95)');
    ctx.fillStyle = deskG;
    ctx.strokeStyle = 'rgba(78, 205, 196, 0.32)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(top.x, top.y, w * 0.52, h * 0.32, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    const mon = project(wx, 0.72, wz - 0.08);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
    ctx.strokeStyle = 'rgba(78, 205, 196, 0.45)';
    ctx.lineWidth = 1;
    const mw = 14 * zoom;
    const mh = 10 * zoom;
    if (typeof ctx.roundRect === 'function') {
      ctx.beginPath();
      ctx.roundRect(mon.x - mw / 2, mon.y - mh, mw, mh, 2 * zoom);
      ctx.fill();
      ctx.stroke();
    } else {
      ctx.fillRect(mon.x - mw / 2, mon.y - mh, mw, mh);
      ctx.strokeRect(mon.x - mw / 2, mon.y - mh, mw, mh);
    }
    const glow = ctx.createRadialGradient(mon.x, mon.y - mh * 0.5, 0, mon.x, mon.y - mh * 0.5, 22 * zoom);
    glow.addColorStop(0, 'rgba(78, 205, 196, 0.35)');
    glow.addColorStop(1, 'rgba(78, 205, 196, 0)');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(mon.x, mon.y - mh * 0.5, 22 * zoom, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawPoi(key) {
    const poi = POIs[key];
    const p = project(poi.x, 0, poi.z);
    ctx.font = `${Math.round(18 * zoom)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(poi.label, p.x, p.y - 8 * zoom);
    ctx.font = `${Math.round(10 * zoom)}px sans-serif`;
    ctx.fillStyle = 'rgba(148, 163, 184, 0.85)';
    const labels = { coffee: '茶水间', lounge: '休息区', door: '入口' };
    ctx.fillText(labels[key] || '', p.x, p.y + 12 * zoom);
  }

  function drawCharacter(ch, t) {
    const p = project(ch.x, ch.y, ch.z);
    const scale = zoom;
    const active = ch.status !== 'idle';
    const selected = ch.id === selectedId;
    const ring = selected
      ? '#4ecdc4'
      : (active ? (ch.status === 'working' ? '#4ade80' : '#fbbf24') : 'rgba(148,163,184,0.35)');

    ctx.beginPath();
    ctx.ellipse(p.x, p.y + 10 * scale, 14 * scale, 6 * scale, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(p.x, p.y - 14 * scale, 16 * scale, 0, Math.PI * 2);
    const headG = ctx.createRadialGradient(p.x - 4 * scale, p.y - 18 * scale, 2, p.x, p.y - 14 * scale, 18 * scale);
    headG.addColorStop(0, 'rgba(30, 41, 59, 0.98)');
    headG.addColorStop(1, 'rgba(15, 23, 42, 0.92)');
    ctx.fillStyle = headG;
    ctx.fill();
    ctx.strokeStyle = ring;
    ctx.lineWidth = active ? 2.5 : 1.2;
    ctx.stroke();

    ctx.font = `${Math.round(18 * scale)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let icon = ch.icon;
    if (ch.status === 'idle' && ch.behavior === 'nap' && ch.walkT === 0) icon = '😴';
    if (ch.status === 'idle' && ch.behavior === 'stretch' && ch.walkT === 0) icon = '🧘';
    ctx.fillText(icon, p.x, p.y - 14 * scale);

    ctx.font = `600 ${Math.round(10 * scale)}px system-ui, sans-serif`;
    ctx.fillStyle = '#e2e8f0';
    ctx.fillText(ch.name, p.x, p.y + 6 * scale);

    const statusText = ch.status === 'working' && ch.tool
      ? ch.tool
      : (STATUS_LABEL[ch.status] || ch.status);
    ctx.font = `${Math.round(9 * scale)}px system-ui, sans-serif`;
    ctx.fillStyle = active ? '#86efac' : '#94a3b8';
    ctx.fillText(statusText, p.x, p.y + 18 * scale);

    if (ch.bubbleT > 0 && ch.bubble) {
      const bw = ctx.measureText(ch.bubble).width + 14 * scale;
      const bx = p.x - bw / 2;
      const by = p.y - 44 * scale;
      const bh = 18 * scale;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
      ctx.strokeStyle = 'rgba(78, 205, 196, 0.45)';
      ctx.lineWidth = 1;
      if (typeof ctx.roundRect === 'function') {
        ctx.beginPath();
        ctx.roundRect(bx, by, bw, bh, 6 * scale);
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.fillRect(bx, by, bw, bh);
        ctx.strokeRect(bx, by, bw, bh);
      }
      ctx.font = `${Math.round(9 * scale)}px system-ui, sans-serif`;
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(ch.bubble, p.x, by + 9 * scale);
    }

    hitTargets.push({
      id: ch.id,
      x: p.x,
      y: p.y - 14 * scale,
      r: Math.max(18 * scale, 16),
    });
  }

  function drawEmptyState() {
    ctx.font = '600 14px system-ui, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.textAlign = 'center';
    ctx.fillText('正在加载专员…', width / 2, height / 2 - 8);
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillStyle = 'rgba(148, 163, 184, 0.75)';
    ctx.fillText('连接后会显示 9 位内置专员', width / 2, height / 2 + 14);
    ctx.textAlign = 'left';
  }

  function renderFrame(t) {
    if (!ctx || !canvas) return;
    const now = t / 1000;
    const dt = Math.min(0.05, now - lastT || 0.016);
    lastT = now;

    ctx.clearRect(0, 0, width, height);
    hitTargets = [];
    drawBackdrop();
    drawWalls();
    drawFloor();
    if (!reducedMotion) drawAmbientParticles(now);
    Object.keys(POIs).forEach(drawPoi);

    const deskDrawn = new Set();
    for (const ch of characters.values()) {
      const key = `${ch.deskX.toFixed(2)}:${ch.deskZ.toFixed(2)}`;
      if (!deskDrawn.has(key)) {
        drawDesk(ch.deskX, ch.deskZ);
        deskDrawn.add(key);
      }
    }

    const sorted = [...characters.values()].sort((a, b) => (a.x + a.z) - (b.x + b.z));
    if (!reducedMotion && !drivingPaused) {
      sorted.forEach((ch) => updateCharacter(ch, dt, now));
    }
    sorted.forEach((ch) => drawCharacter(ch, now));

    if (!characters.size) {
      drawEmptyState();
    }

    if (drivingPaused) {
      ctx.fillStyle = 'rgba(8, 12, 20, 0.55)';
      ctx.fillRect(0, 0, width, height);
      ctx.font = '600 13px system-ui, sans-serif';
      ctx.fillStyle = '#fbbf24';
      ctx.textAlign = 'center';
      ctx.fillText('行驶中 · 办公室动画已暂停', width / 2, height / 2 - 6);
      ctx.font = '11px system-ui, sans-serif';
      ctx.fillStyle = 'rgba(148, 163, 184, 0.9)';
      ctx.fillText('不影响辅助驾驶 · 停车后可恢复动画', width / 2, height / 2 + 14);
      ctx.textAlign = 'left';
      return;
    }

    ctx.font = '11px system-ui, sans-serif';
    ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
    ctx.textAlign = 'left';
    ctx.fillText('拖拽平移 · 滚轮缩放', 10, height - 10);
  }

  function loop(t) {
    if (!running) return;
    if (document.hidden) {
      rafId = requestAnimationFrame(loop);
      return;
    }
    if (!drivingPaused && !reducedMotion && t - lastFrameMs < FPS_MS) {
      rafId = requestAnimationFrame(loop);
      return;
    }
    lastFrameMs = t;
    renderFrame(t);
    rafId = requestAnimationFrame(loop);
  }

  function resize() {
    if (!canvas) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.getBoundingClientRect();
    width = Math.max(280, rect.width);
    height = Math.max(200, rect.height);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function pickAgentAt(clientX, clientY) {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    for (let i = hitTargets.length - 1; i >= 0; i -= 1) {
      const t = hitTargets[i];
      if (Math.hypot(x - t.x, y - t.y) <= t.r) return t.id;
    }
    return null;
  }

  function onPointerDown(ev) {
    if (ev.pointerType === 'touch' && ev.isPrimary === false) return;
    drag = { x: ev.clientX - panX, y: ev.clientY - panY, moved: false, x0: ev.clientX, y0: ev.clientY };
    canvas.setPointerCapture(ev.pointerId);
  }

  function onPointerMove(ev) {
    if (!drag) return;
    if (Math.hypot(ev.clientX - drag.x0, ev.clientY - drag.y0) > 4) drag.moved = true;
    panX = ev.clientX - drag.x;
    panY = ev.clientY - drag.y;
  }

  function onPointerUp(ev) {
    if (drag && !drag.moved) {
      const id = pickAgentAt(ev.clientX, ev.clientY);
      if (id) {
        selectedId = id;
        onSelectAgent?.(id);
        renderFrame(performance.now());
      }
    }
    drag = null;
    try { canvas.releasePointerCapture(ev.pointerId); } catch {}
  }

  function onWheel(ev) {
    ev.preventDefault();
    const factor = ev.deltaY > 0 ? 0.92 : 1.08;
    zoom = Math.min(1.6, Math.max(0.65, zoom * factor));
  }

  function start() {
    if (running || !canvas) return;
    running = true;
    lastT = 0;
    rafId = requestAnimationFrame(loop);
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
  }

  function init(el) {
    canvas = el || document.getElementById('officeSceneCanvas');
    if (!canvas) return false;
    ctx = canvas.getContext('2d');
    reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    resize();
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return true;
  }

  function onVisibilityChange() {
    if (!document.hidden && running && !drivingPaused) {
      lastFrameMs = 0;
      renderFrame(performance.now());
    }
  }

  function setDrivingPaused(paused) {
    drivingPaused = !!paused;
    if (running && canvas && ctx) {
      lastFrameMs = 0;
      renderFrame(performance.now());
    }
  }

  function setAgents(list) {
    syncAgents(list);
  }

  function applyOffice(data) {
    officeState = data || null;
    applyLiveStatus();
  }

  function destroy() {
    stop();
    if (!canvas) return;
    canvas.removeEventListener('pointerdown', onPointerDown);
    canvas.removeEventListener('pointermove', onPointerMove);
    canvas.removeEventListener('pointerup', onPointerUp);
    canvas.removeEventListener('pointercancel', onPointerUp);
    canvas.removeEventListener('wheel', onWheel);
    window.removeEventListener('resize', resize);
    document.removeEventListener('visibilitychange', onVisibilityChange);
    canvas = null;
    ctx = null;
    characters.clear();
  }

  function setSelectedAgent(id) {
    selectedId = id || null;
    if (running && canvas && ctx) renderFrame(performance.now());
  }

  function setOnSelectAgent(fn) {
    onSelectAgent = typeof fn === 'function' ? fn : null;
  }

  return {
    init,
    destroy,
    start,
    stop,
    resize,
    setAgents,
    applyOffice,
    setDrivingPaused,
    setSelectedAgent,
    setOnSelectAgent,
  };
})();
