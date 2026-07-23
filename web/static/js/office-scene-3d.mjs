/**
 * OP 办公室 — Three.js 完整 3D（OrbitControls + GLTF + 动画角色）
 */
import * as THREE from '/static/vendor/three/three.module.js';
import { OrbitControls } from '/static/vendor/three/examples/jsm/controls/OrbitControls.js';

const IDLE_BEHAVIORS = ['desk', 'coffee', 'walk', 'stretch', 'nap'];
const STATUS_LABEL = {
  idle: '空闲',
  assigned: '已派活',
  working: '执行中',
  waiting: '待确认',
};

const AGENT_COLORS = {
  op: 0xff6b6b,
  triage: 0xfbbf24,
  tune: 0x4ecdc4,
  route: 0x60a5fa,
  adapt: 0xa78bfa,
  secoc: 0xf472b6,
  devops: 0x94a3b8,
  cloud: 0x38bdf8,
  pc: 0x34d399,
};

const ROOM = {
  floorW: 14,
  floorH: 11,
  deskCols: 3,
  deskGapX: 3.0,
  deskGapZ: 2.4,
  deskOriginX: -3.0,
  deskOriginZ: 2.0,
};

/** openpilot 主题区域 — 专员 idle 时会走向对应 POI */
const ZONE_POIS = {
  obd: { x: -6.1, z: -3.2 },
  offroad: { x: -6.0, z: 0.2 },
  engage: { x: 0, z: -4.6 },
  replay: { x: 5.8, z: -2.2 },
  alertWall: { x: -5.6, z: -1.8 },
  steering: { x: 3.6, z: -3.1 },
  routeWall: { x: -0.8, z: -4.9 },
  secoc: { x: 3.2, z: 2.6 },
  adapt: { x: 0.4, z: 4.6 },
  ci: { x: -2.6, z: -4.4 },
  cloud: { x: 2.6, z: 4.9 },
  coffee: { x: -5.2, z: 4.2 },
  lounge: { x: 5.4, z: 4.0 },
  door: { x: 0, z: -5.0 },
};

const POIs = ZONE_POIS;

const AGENT_ZONE = {
  op: 'engage',
  triage: 'alertWall',
  tune: 'steering',
  route: 'routeWall',
  adapt: 'adapt',
  secoc: 'secoc',
  devops: 'ci',
  cloud: 'cloud',
  pc: 'replay',
};

/** 场景中可动画 / 可刷新的引用 */
const sceneRefs = {
  gateArms: [],
  gateLight: null,
  laneFlow: [],
  alertPanel: null,
  routeWallMat: null,
  offroadCar: null,
  trafficLight: null,
  deskScreens: [],
  ciLights: [],
  vehicleState: null,
  driving: false,
  flowPhase: 0,
};

let mount = null;
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let clock = null;
let running = false;
let rafId = 0;
let officeState = null;
let characters = new Map();
let agentRigs = new Map();
let pickables = [];
let selectedId = null;
let onSelectAgent = null;
let reducedMotion = false;
let drivingPaused = false;
let lastFrameMs = 0;
const FPS_CAP = 30;
const FPS_MS = 1000 / FPS_CAP;
let raycaster = null;
let pointer = null;
let resizeObserver = null;
let clickDrag = null;
let assetKit = null;

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: opts.roughness ?? 0.78,
    metalness: opts.metalness ?? 0.05,
    emissive: opts.emissive || 0x000000,
    emissiveIntensity: opts.emissiveIntensity ?? 0,
    flatShading: !!opts.flat,
    transparent: !!opts.transparent,
    opacity: opts.opacity ?? 1,
  });
}

function box(w, h, d, color, opts = {}) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, opts));
  mesh.castShadow = opts.noShadow !== true;
  mesh.receiveShadow = true;
  return mesh;
}

function hashBehavior(id) {
  let h = 0;
  const s = String(id || '');
  for (let i = 0; i < s.length; i += 1) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return IDLE_BEHAVIORS[Math.abs(h) % IDLE_BEHAVIORS.length];
}

function deskSlot(index) {
  const col = index % ROOM.deskCols;
  const row = Math.floor(index / ROOM.deskCols);
  return {
    x: ROOM.deskOriginX + col * ROOM.deskGapX,
    z: ROOM.deskOriginZ - row * ROOM.deskGapZ,
    row,
    col,
  };
}

function agentDeskPos(agent, index) {
  const desk = agent?.desk || {};
  if (Number.isFinite(desk.col) && Number.isFinite(desk.row)) {
    return {
      x: ROOM.deskOriginX + desk.col * ROOM.deskGapX,
      z: ROOM.deskOriginZ - desk.row * ROOM.deskGapZ,
    };
  }
  const slot = deskSlot(index);
  return { x: slot.x, z: slot.z };
}

function agentColor(id) {
  return AGENT_COLORS[id] || 0x4ecdc4;
}

class AssetKit {
  constructor() {
    this.templates = new Map();
    this.loader = null;
  }

  async ensureLoader() {
    if (this.loader) return this.loader;
    try {
      const mod = await import('/static/vendor/three/examples/jsm/loaders/GLTFLoader.js');
      this.loader = new mod.GLTFLoader();
    } catch (e) {
      console.warn('OfficeScene: GLTFLoader unavailable, using procedural props only', e);
      this.loader = null;
    }
    return this.loader;
  }

  async load() {
    let manifest = { models: {} };
    try {
      const res = await fetch('/static/vendor/office/manifest.json');
      if (res.ok) manifest = await res.json();
    } catch { /* procedural only */ }

    const loader = await this.ensureLoader();
    if (!loader) return;

    const base = manifest.base || '/static/vendor/office/';
    const entries = Object.entries(manifest.models || {});
    await Promise.all(entries.map(async ([key, spec]) => {
      const url = `${base}${spec.file}`;
      try {
        const gltf = await this.loader.loadAsync(url);
        const root = gltf.scene;
        root.traverse((o) => {
          if (o.isMesh) {
            o.castShadow = true;
            o.receiveShadow = true;
          }
        });
        this.templates.set(key, { root, spec });
      } catch {
        this.templates.set(key, null);
      }
    }));
  }

  clone(key, x, z, rotY = 0, scaleMul = 1) {
    const tpl = this.templates.get(key);
    if (!tpl?.root) return null;
    const g = tpl.root.clone(true);
    const s = (tpl.spec.scale || 1) * scaleMul;
    g.scale.setScalar(s);
    g.position.set(x, tpl.spec.y || 0, z);
    g.rotation.y = rotY;
    scene.add(g);
    return g;
  }

  has(key) {
    return !!this.templates.get(key)?.root;
  }
}

function placeAsset(key, x, z, rotY = 0, scaleMul = 1) {
  return assetKit?.clone(key, x, z, rotY, scaleMul) || null;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function createEmojiSprite(emoji, scale = 0.58) {
  const size = 96;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.font = `${Math.round(size * 0.72)}px "Segoe UI Emoji", "Apple Color Emoji", sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(emoji, size / 2, size / 2 + 4);
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sprite.scale.set(scale, scale, 1);
  sprite.renderOrder = 10;
  return sprite;
}

function createLabelSprite(lines, { active = false, selected = false, compact = false } = {}) {
  const padY = compact ? 5 : 6;
  const lineH = compact ? 14 : 16;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const width = compact ? 168 : 190;
  const height = padY * 2 + lineH * lines.length;
  canvas.width = width;
  canvas.height = height;
  ctx.fillStyle = selected
    ? 'rgba(78, 205, 196, 0.24)'
    : (active ? 'rgba(74, 222, 128, 0.18)' : 'rgba(15, 23, 42, 0.78)');
  ctx.strokeStyle = selected
    ? 'rgba(78, 205, 196, 0.85)'
    : (active ? 'rgba(74, 222, 128, 0.55)' : 'rgba(148, 163, 184, 0.35)');
  ctx.lineWidth = 1.5;
  roundRect(ctx, 1, 1, width - 2, height - 2, 8);
  ctx.fill();
  ctx.stroke();
  ctx.textAlign = 'center';
  lines.forEach((line, i) => {
    const y = padY + lineH * i + lineH * 0.72;
    ctx.font = i === 0
      ? `600 ${compact ? 12 : 13}px system-ui, sans-serif`
      : `${compact ? 10 : 11}px system-ui, sans-serif`;
    ctx.fillStyle = i === 0 ? '#f1f5f9' : (active ? '#86efac' : '#94a3b8');
    ctx.fillText(line, width / 2, y);
  });
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  const scaleY = compact ? 1.05 : 1.2;
  sprite.scale.set(scaleY * (width / height), scaleY, 1);
  sprite.position.y = compact ? 1.35 : 1.48;
  sprite.renderOrder = 11;
  return sprite;
}

function createAreaSign(title, emoji, sub = '') {
  const canvas = document.createElement('canvas');
  canvas.width = 168;
  canvas.height = sub ? 54 : 44;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(15, 23, 42, 0.82)';
  roundRect(ctx, 2, 2, 164, canvas.height - 4, 8);
  ctx.fill();
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
  ctx.lineWidth = 1;
  roundRect(ctx, 2, 2, 164, canvas.height - 4, 8);
  ctx.stroke();
  ctx.font = '16px "Segoe UI Emoji", sans-serif';
  ctx.fillText(emoji, 14, sub ? 26 : 28);
  ctx.font = '600 11px system-ui, sans-serif';
  ctx.fillStyle = '#e2e8f0';
  ctx.fillText(title, 36, sub ? 24 : 28);
  if (sub) {
    ctx.font = '9px system-ui, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(sub, 36, 40);
  }
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sprite.scale.set(1.05, 0.32 * (canvas.height / 44), 1);
  sprite.position.y = 0.04;
  return sprite;
}

function createZonePin(emoji) {
  const sprite = createEmojiSprite(emoji, 0.38);
  sprite.position.y = 0.1;
  return sprite;
}

function createScreenTexture(kind, extra = '') {
  const w = 256;
  const h = 144;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, '#0f172a');
  grad.addColorStop(1, '#1e293b');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  if (kind === 'route') {
    ctx.strokeStyle = '#4ecdc4';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(24, 110);
    for (let i = 0; i < 8; i += 1) {
      const x = 24 + i * 28;
      const y = 110 - Math.sin(i * 0.9) * 42 - i * 4;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.fillStyle = '#86efac';
    ctx.beginPath();
    ctx.arc(210, 38, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#94a3b8';
    ctx.font = '600 13px system-ui,sans-serif';
    ctx.fillText('ROUTE · qlog', 14, 24);
  } else if (kind === 'comma') {
    ctx.fillStyle = '#4ecdc4';
    ctx.font = '700 28px system-ui,sans-serif';
    ctx.fillText('comma', 18, 52);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px system-ui,sans-serif';
    ctx.fillText('openpilot · AGNOS', 18, 76);
    ctx.strokeStyle = 'rgba(78,205,196,0.5)';
    ctx.strokeRect(12, 12, w - 24, h - 24);
  } else if (kind === 'alert') {
    ctx.fillStyle = '#fbbf24';
    ctx.font = '600 14px system-ui,sans-serif';
    const lines = (extra || '无告警').slice(0, 48);
    ctx.fillText(lines, 14, 40, w - 28);
    ctx.fillStyle = '#64748b';
    ctx.font = '11px system-ui,sans-serif';
    ctx.fillText('ALERT · triage', 14, 22);
  } else if (kind === 'tool') {
    ctx.fillStyle = '#4ade80';
    ctx.font = '600 13px monospace';
    const tool = (extra || 'running…').slice(0, 40);
    ctx.fillText(tool, 14, 56, w - 28);
    ctx.fillStyle = '#64748b';
    ctx.font = '11px system-ui,sans-serif';
    ctx.fillText('TOOL EXEC', 14, 28);
    const barW = (w - 28) * (0.35 + 0.25 * Math.sin(performance.now() / 200));
    ctx.fillStyle = 'rgba(74,222,128,0.35)';
    ctx.fillRect(14, 72, barW, 8);
  } else {
    ctx.fillStyle = '#4ecdc4';
    ctx.font = '12px system-ui,sans-serif';
    ctx.fillText('OP DESK', 14, 40);
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function refreshAlertPanel() {
  if (!sceneRefs.alertPanel) return;
  const alert = sceneRefs.vehicleState?.alert_text1
    || sceneRefs.vehicleState?.alertText1
    || '待机 · 无告警';
  const tex = createScreenTexture('alert', alert);
  const old = sceneRefs.alertPanel.material.map;
  sceneRefs.alertPanel.material.map = tex;
  sceneRefs.alertPanel.material.needsUpdate = true;
  old?.dispose?.();
}

function refreshRouteWall() {
  if (!sceneRefs.routeWallMat) return;
  const tex = createScreenTexture('route');
  const old = sceneRefs.routeWallMat.map;
  sceneRefs.routeWallMat.map = tex;
  sceneRefs.routeWallMat.needsUpdate = true;
  old?.dispose?.();
}

function pulseDeskScreens(toolName) {
  for (const entry of sceneRefs.deskScreens) {
    const tex = createScreenTexture('tool', toolName || '…');
    const old = entry.mat.map;
    entry.mat.map = tex;
    entry.mat.emissive = new THREE.Color(0x4ade80);
    entry.mat.emissiveIntensity = 0.35;
    entry.mat.needsUpdate = true;
    entry.pulseT = 2.5;
    old?.dispose?.();
  }
}

function updateGateFromVehicle() {
  const vs = sceneRefs.vehicleState || {};
  const active = !!vs.active;
  const engageable = !!vs.engageable;
  const enabled = !!vs.enabled;
  const open = active || (engageable && !enabled);
  let color = 0x94a3b8;
  if (active) color = 0x4ade80;
  else if (engageable) color = 0xfbbf24;
  else if (enabled) color = 0x60a5fa;
  const angle = open ? Math.PI / 2.2 : 0.12;
  sceneRefs.gateArms.forEach((arm, i) => {
    arm.rotation.y = (i === 0 ? 1 : -1) * angle;
  });
  if (sceneRefs.gateLight) {
    sceneRefs.gateLight.material.emissive.setHex(color);
    sceneRefs.gateLight.material.emissiveIntensity = active ? 0.85 : 0.45;
  }
  if (sceneRefs.trafficLight) {
    sceneRefs.trafficLight.traverse((o) => {
      if (!o.isMesh || !o.material) return;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach((m) => {
        if (!m.emissive) return;
        m.emissive.setHex(color);
        m.emissiveIntensity = active ? 0.9 : engageable ? 0.55 : 0.25;
      });
    });
  }
}

function proceduralCar(x, z, rotY = 0) {
  const g = new THREE.Group();
  g.position.set(x, 0, z);
  g.rotation.y = rotY;
  const body = box(1.6, 0.42, 3.2, 0x334155, { metalness: 0.35, roughness: 0.55 });
  body.position.y = 0.38;
  g.add(body);
  const cabin = box(1.35, 0.38, 1.5, 0x1e293b, { metalness: 0.2 });
  cabin.position.set(0, 0.78, -0.15);
  g.add(cabin);
  const windshield = new THREE.Mesh(
    new THREE.PlaneGeometry(1.2, 0.32),
    new THREE.MeshStandardMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.55, metalness: 0.1 }),
  );
  windshield.position.set(0, 0.82, 0.58);
  windshield.rotation.x = -0.35;
  g.add(windshield);
  [[-0.72, 0.18, 1.0], [0.72, 0.18, 1.0], [-0.72, 0.18, -1.0], [0.72, 0.18, -1.0]].forEach(([wx, wy, wz]) => {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.14, 14), mat(0x0f172a, { metalness: 0.5 }));
    wheel.rotation.z = Math.PI / 2;
    wheel.position.set(wx, wy, wz);
    g.add(wheel);
  });
  const comma = new THREE.Mesh(
    new THREE.PlaneGeometry(0.5, 0.12),
    new THREE.MeshBasicMaterial({ color: 0x4ecdc4 }),
  );
  comma.position.set(0, 0.55, 1.62);
  g.add(comma);
  return g;
}

function createAccessory(agentId, color) {
  const g = new THREE.Group();
  const c = color;
  switch (agentId) {
    case 'op': {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.02, 8, 20), mat(c, { emissive: c, emissiveIntensity: 0.3 }));
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 0.98;
      g.add(ring);
      break;
    }
    case 'triage': {
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.22, 4), mat(0xfbbf24, { flat: true }));
      cone.position.y = 1.05;
      g.add(cone);
      break;
    }
    case 'tune': {
      for (let i = -1; i <= 1; i += 1) {
        const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.03, 10), mat(c));
        knob.position.set(i * 0.09, 0.72, 0.14);
        g.add(knob);
      }
      break;
    }
    case 'route': {
      const chart = box(0.18, 0.24, 0.02, 0xffffff);
      chart.position.set(0.22, 0.75, 0.1);
      g.add(chart);
      break;
    }
    case 'adapt': {
      const bar = box(0.28, 0.04, 0.04, 0x94a3b8, { metalness: 0.5 });
      bar.position.set(0.2, 0.78, 0.08);
      bar.rotation.z = Math.PI / 4;
      g.add(bar);
      break;
    }
    case 'secoc': {
      const lock = box(0.1, 0.12, 0.05, c, { metalness: 0.3 });
      lock.position.set(0, 0.95, 0.12);
      g.add(lock);
      break;
    }
    case 'devops': {
      const gear = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.025, 8, 16), mat(0x94a3b8, { metalness: 0.4 }));
      gear.position.set(0.18, 0.92, 0.1);
      g.add(gear);
      break;
    }
    case 'cloud': {
      [[0, 0], [-0.07, 0.03], [0.07, 0.03]].forEach(([x, z]) => {
        const puff = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 8), mat(0x38bdf8, { flat: true }));
        puff.position.set(x, 1.0, z);
        g.add(puff);
      });
      break;
    }
    case 'pc': {
      const laptop = box(0.22, 0.02, 0.16, 0x334155);
      laptop.position.set(0.2, 0.72, 0.12);
      g.add(laptop);
      break;
    }
    default:
      break;
  }
  return g;
}

function createAgentRig(ch) {
  const group = new THREE.Group();
  group.userData.agentId = ch.id;

  const shadow = new THREE.Mesh(
    new THREE.CircleGeometry(0.3, 24),
    new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.24 }),
  );
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.02;
  group.add(shadow);

  const bodyMat = mat(0x1e293b, { roughness: 0.55 });
  const legGeo = new THREE.CylinderGeometry(0.065, 0.07, 0.4, 8);
  legGeo.translate(0, -0.2, 0);
  const legL = new THREE.Mesh(legGeo, bodyMat);
  legL.position.set(-0.11, 0.42, 0);
  legL.castShadow = true;
  const legR = legL.clone();
  legR.position.x = 0.11;

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.26, 0.44, 12), bodyMat);
  torso.position.y = 0.68;
  torso.castShadow = true;

  const armGeo = new THREE.CylinderGeometry(0.045, 0.05, 0.32, 8);
  armGeo.translate(0, -0.16, 0);
  const armL = new THREE.Mesh(armGeo, bodyMat);
  armL.position.set(-0.28, 0.82, 0);
  armL.rotation.z = 0.25;
  const armR = armL.clone();
  armR.position.x = 0.28;
  armR.rotation.z = -0.25;

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.19, 16, 16), mat(0x0f172a, { roughness: 0.4 }));
  head.position.y = 1.02;
  head.castShadow = true;

  const scarf = new THREE.Mesh(
    new THREE.TorusGeometry(0.22, 0.045, 10, 24),
    mat(ch.color, { emissive: ch.color, emissiveIntensity: 0.28, roughness: 0.4 }),
  );
  scarf.rotation.x = Math.PI / 2;
  scarf.position.y = 0.82;

  const emoji = createEmojiSprite(ch.icon);
  emoji.position.y = 1.02;

  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.36, 0.42, 32),
    new THREE.MeshBasicMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.5, side: THREE.DoubleSide }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.025;

  const accessory = createAccessory(ch.id, ch.color);
  const hit = new THREE.Mesh(
    new THREE.CylinderGeometry(0.36, 0.36, 1.2, 12),
    new THREE.MeshBasicMaterial({ visible: false }),
  );
  hit.position.y = 0.6;
  hit.userData.agentId = ch.id;

  [legL, legR, torso, armL, armR, head, scarf, emoji, ring, accessory, hit].forEach((o) => group.add(o));
  pickables.push(hit);
  scene.add(group);

  const rig = {
    group,
    parts: { legL, legR, armL, armR, torso, head, scarf, emoji, ring, accessory, hit },
    label: null,
    labelSig: '',
  };
  agentRigs.set(ch.id, rig);
  return rig;
}

function animateRig(rig, ch, walking) {
  const { parts } = rig;
  if (walking) {
    const swing = Math.sin(ch.walkT) * 0.65;
    parts.legL.rotation.x = swing;
    parts.legR.rotation.x = -swing;
    parts.armL.rotation.x = -swing * 0.55;
    parts.armR.rotation.x = swing * 0.55;
    parts.torso.rotation.z = Math.sin(ch.walkT * 0.5) * 0.04;
  } else {
    parts.legL.rotation.x = 0;
    parts.legR.rotation.x = 0;
    parts.armL.rotation.x = ch.status === 'working' ? -0.35 : 0;
    parts.armR.rotation.x = ch.status === 'working' ? -0.35 : 0;
    parts.torso.rotation.z = 0;
  }

  if (ch.status === 'idle' && ch.behavior === 'nap' && !walking) {
    parts.torso.rotation.x = 0.35;
    parts.head.position.y = 0.88;
  } else {
    parts.torso.rotation.x = 0;
    parts.head.position.y = 1.02;
  }
}

function buildWorkstation(x, z, screenKind = 'comma') {
  const hasDesk = assetKit?.has('desk');
  if (!hasDesk) {
    proceduralDesk(x, z, screenKind);
    return;
  }
  placeAsset('desk', x, z, 0, 1);
  placeAsset('chair', x, z + 0.58, Math.PI, 1);
  placeAsset('monitor', x, z - 0.18, 0, 1);
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.42, 0.26),
    new THREE.MeshStandardMaterial({
      map: createScreenTexture(screenKind === 'route' ? 'route' : 'comma'),
      emissive: 0x4ecdc4,
      emissiveIntensity: 0.15,
      roughness: 0.35,
    }),
  );
  screen.position.set(x, 1.02, z - 0.28);
  scene.add(screen);
  sceneRefs.deskScreens.push({ mat: screen.material, pulseT: 0 });
}

function proceduralDesk(x, z, screenKind = 'comma') {
  const g = new THREE.Group();
  g.position.set(x, 0, z);
  const top = box(1.6, 0.08, 0.85, 0xf8fafc, { flat: true });
  top.position.y = 0.76;
  g.add(top);
  [[-0.65, -0.32], [0.65, -0.32], [-0.65, 0.32], [0.65, 0.32]].forEach(([lx, lz]) => {
    const leg = box(0.08, 0.76, 0.08, 0xcbd5e1);
    leg.position.set(lx, 0.38, lz);
    g.add(leg);
  });
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.48, 0.28),
    new THREE.MeshStandardMaterial({
      map: createScreenTexture(screenKind === 'route' ? 'route' : 'comma'),
      emissive: 0x4ecdc4,
      emissiveIntensity: 0.12,
      roughness: 0.4,
    }),
  );
  screen.position.set(0, 1.05, -0.168);
  g.add(screen);
  sceneRefs.deskScreens.push({ mat: screen.material, pulseT: 0 });
  const seat = box(0.44, 0.08, 0.44, 0x475569);
  seat.position.set(0, 0.44, 0.58);
  g.add(seat);
  scene.add(g);
}

function buildBreakRoom() {
  const g = new THREE.Group();
  if (!placeAsset('coffeeMachine', -6.1, 4.15, Math.PI)) {
    const machine = box(0.5, 0.6, 0.38, 0x1e293b, { metalness: 0.35 });
    machine.position.set(-6.1, 1.05, 4.15);
    g.add(machine);
  }
  if (!placeAsset('coffeeTable', -5.1, 4.45, 0)) {
    const counter = box(3.0, 0.95, 0.6, 0xffffff, { flat: true });
    counter.position.set(-5.3, 0.48, 4.3);
    g.add(counter);
  }
  placeAsset('plant', -4.4, 4.6, -Math.PI / 4, 0.75);
  const sign = createAreaSign('茶水间', '☕');
  sign.position.set(-5.2, 0, 5.1);
  g.add(sign);
  scene.add(g);
}

function buildLounge() {
  const g = new THREE.Group();
  if (!placeAsset('sofa', 5.4, 4.1, Math.PI)) {
    const sofa = box(2.0, 0.45, 0.78, 0xe2e8f0, { flat: true });
    sofa.position.set(5.4, 0.28, 4.1);
    g.add(sofa);
  }
  if (!placeAsset('coffeeTable', 4.5, 4.55, 0)) {
    const table = box(0.6, 0.3, 0.6, 0xffffff, { flat: true });
    table.position.set(4.5, 0.15, 4.55);
    g.add(table);
  }
  if (!placeAsset('plant', 6.2, 3.5, 0, 0.85)) {
    const pot = box(0.24, 0.2, 0.24, 0x78350f);
    pot.position.set(6.2, 0.1, 3.5);
    g.add(pot);
  }
  const sign = createAreaSign('休息区', '🛋');
  sign.position.set(5.4, 0, 5.1);
  g.add(sign);
  scene.add(g);
}

function buildReplayTrack() {
  const { x, z } = ZONE_POIS.replay;
  const hasTrack = assetKit?.has('trackStraight');
  if (hasTrack) {
    placeAsset('trackStart', x - 0.85, z, Math.PI / 2);
    placeAsset('trackStraight', x, z, Math.PI / 2);
    placeAsset('trackStraight', x + 1.7, z, Math.PI / 2);
    placeAsset('trackCorner', x + 2.55, z - 0.85, 0);
    placeAsset('raceBarrier', x + 2.85, z + 0.55, Math.PI / 2);
    placeAsset('flagCheckers', x + 1.15, z - 1.15, 0);
    placeAsset('vehicle', x + 0.35, z + 0.15, -Math.PI / 2, 0.75);
  } else {
    const g = new THREE.Group();
    const base = box(1.3, 0.2, 2.3, 0x334155, { metalness: 0.2 });
    base.position.set(x, 0.14, z);
    g.add(base);
    scene.add(g);
  }
  const sign = createAreaSign('Replay', '🏎️');
  sign.position.set(x, 0, z - 1.35);
  scene.add(sign);
}

function buildWallsAndWindows() {
  const h = 2.7;
  const hw = ROOM.floorW / 2;
  const hh = ROOM.floorH / 2;

  const back = box(ROOM.floorW + 0.12, h, 0.12, 0xffffff, { flat: true });
  back.position.set(0, h / 2, -hh);
  scene.add(back);

  const left = box(0.12, h, ROOM.floorH, 0xf8fafc, { flat: true });
  left.position.set(-hw, h / 2, 0);
  scene.add(left);

  const right = box(0.12, h, ROOM.floorH, 0xf8fafc, { flat: true });
  right.position.set(hw, h / 2, 0);
  scene.add(right);

  const partition = box(0.1, h * 0.85, 4.5, 0xf1f5f9, { flat: true });
  partition.position.set(-3.2, h * 0.42, 4.0);
  scene.add(partition);

  const glass = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 1.1),
    new THREE.MeshPhysicalMaterial({
      color: 0xbae6fd,
      transparent: true,
      opacity: 0.35,
      roughness: 0.05,
      metalness: 0,
      transmission: 0.55,
      thickness: 0.2,
    }),
  );
  glass.position.set(0, 1.35, -hh + 0.08);
  scene.add(glass);

  const sign = createAreaSign('入口', '🚪');
  sign.position.set(0, 0, -hh + 0.45);
  scene.add(sign);

  for (let i = -2; i <= 2; i += 2) {
    const panel = box(1.2, 0.08, 0.8, 0xffffff, { emissive: 0xfff7ed, emissiveIntensity: 0.35, flat: true });
    panel.position.set(i * 2.2, h - 0.1, 0);
    scene.add(panel);
    const light = new THREE.PointLight(0xfff7ed, 0.25, 8);
    light.position.set(i * 2.2, h - 0.3, 0);
    scene.add(light);
  }
}

function buildFloor() {
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.floorW + 2, ROOM.floorH + 2),
    mat(0x14202e, { roughness: 0.95 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const rug = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 5.2), mat(0x243044, { roughness: 1 }));
  rug.rotation.x = -Math.PI / 2;
  rug.position.set(0, 0.006, 0.6);
  scene.add(rug);

  const tile = 1.85;
  const hasRoads = assetKit?.has('roadStraight');
  if (hasRoads) {
    [-4.6, -2.75, -0.9, 0.95, 2.8].forEach((z) => placeAsset('roadStraight', 0, z, 0));
    placeAsset('roadCrossroadPath', 0, -4.35, 0);
    [-1.85, -3.7].forEach((x) => placeAsset('roadStraight', x, 0.2, Math.PI / 2));
    placeAsset('roadEnd', -5.2, 0.2, Math.PI / 2);
    placeAsset('roadBend', -3.7, -0.95, Math.PI);
    [1.85, 3.7].forEach((x) => placeAsset('roadStraight', x, -2.2, Math.PI / 2));
    placeAsset('streetLight', -6.35, -3.5, 0);
    placeAsset('streetLight', 6.35, -3.5, Math.PI);
    placeAsset('streetLight', -6.35, 3.9, 0);
    placeAsset('streetLight', 6.35, 3.9, Math.PI);
  } else {
    const grid = new THREE.GridHelper(ROOM.floorW, 14, 0x334155, 0x1e293b);
    grid.position.y = 0.01;
    grid.material.transparent = true;
    grid.material.opacity = 0.22;
    scene.add(grid);
  }

  const dashMat = new THREE.MeshBasicMaterial({
    color: 0xfbbf24,
    transparent: true,
    opacity: 0.65,
    side: THREE.DoubleSide,
  });
  for (let i = -3; i <= 3; i += 1) {
    const stripe = new THREE.Mesh(new THREE.PlaneGeometry(0.1, 0.75), dashMat.clone());
    stripe.rotation.x = -Math.PI / 2;
    stripe.position.set(i * (tile * 0.55), 0.014, 0.3);
    scene.add(stripe);
    sceneRefs.laneFlow.push(stripe);
  }
  [-2.05, 2.05].forEach((lx) => {
    const edge = new THREE.Mesh(
      new THREE.PlaneGeometry(0.06, ROOM.floorH - 1.2),
      new THREE.MeshBasicMaterial({ color: 0xf8fafc, transparent: true, opacity: 0.4, side: THREE.DoubleSide }),
    );
    edge.rotation.x = -Math.PI / 2;
    edge.position.set(lx, 0.013, 0.2);
    scene.add(edge);
    sceneRefs.laneFlow.push(edge);
  });
}

function buildEngageGate() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.engage;
  placeAsset('barrier', x - 1.35, z - 0.35, 0);
  placeAsset('barrier', x + 1.35, z - 0.35, Math.PI);
  const tl = placeAsset('trafficLight', x, z, Math.PI);
  sceneRefs.trafficLight = tl;
  if (!tl) {
    const postL = box(0.14, 1.1, 0.14, 0x64748b, { metalness: 0.4 });
    postL.position.set(x - 1.1, 0.55, z);
    const postR = postL.clone();
    postR.position.x = x + 1.1;
    g.add(postL, postR);
    const armGeo = new THREE.BoxGeometry(1.05, 0.08, 0.1);
    const armMat = mat(0xfbbf24, { emissive: 0xfbbf24, emissiveIntensity: 0.35, metalness: 0.3 });
    const armL = new THREE.Mesh(armGeo, armMat);
    armL.position.set(x - 0.55, 0.95, z);
    const armR = new THREE.Mesh(armGeo, armMat.clone());
    armR.position.set(x + 0.55, 0.95, z);
    g.add(armL, armR);
    sceneRefs.gateArms = [armL, armR];
    sceneRefs.gateLight = armL;
  }
  const light = new THREE.PointLight(0xfbbf24, 0.35, 4);
  light.position.set(x, 1.2, z);
  g.add(light);
  const sign = createAreaSign('Engage', '🚧');
  sign.position.set(x, 0, z - 0.75);
  g.add(sign);
  scene.add(g);
}

function buildOffroadBay() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.offroad;
  placeAsset('roadEnd', x, z, Math.PI / 2);
  placeAsset('barrier', x - 0.95, z - 1.15, 0);
  placeAsset('barrier', x + 0.95, z - 1.15, Math.PI);
  const car = placeAsset('vehicle', x, z - 0.15, Math.PI / 2);
  sceneRefs.offroadCar = car || proceduralCar(x, z - 0.15, Math.PI / 2);
  if (!car) g.add(sceneRefs.offroadCar);
  const sign = createAreaSign('Offroad', '🅿️');
  sign.position.set(x, 0, z - 1.65);
  g.add(sign);
  scene.add(g);
}

function buildObdCorner() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.obd;
  placeAsset('cone', x - 0.42, z + 0.38, 0);
  placeAsset('cone', x + 0.42, z + 0.38, 0);
  placeAsset('barrier', x, z - 0.5, 0);
  const bench = box(1.1, 0.55, 0.55, 0xe2e8f0, { flat: true });
  bench.position.set(x, 0.28, z);
  g.add(bench);
  const dongle = box(0.18, 0.08, 0.35, 0x0f172a, { metalness: 0.4 });
  dongle.position.set(x, 0.6, z);
  g.add(dongle);
  const sign = createZonePin('🔌');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildAlertWall() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.alertWall;
  const panel = box(1.8, 1.0, 0.08, 0x0f172a);
  panel.position.set(x, 1.05, z);
  g.add(panel);
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(1.65, 0.88),
    new THREE.MeshStandardMaterial({ map: createScreenTexture('alert', '待机'), emissive: 0xfbbf24, emissiveIntensity: 0.15 }),
  );
  screen.position.set(x, 1.05, z + 0.05);
  g.add(screen);
  sceneRefs.alertPanel = screen;
  const sign = createZonePin('🚦');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildSteeringStation() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.steering;
  const stand = box(0.5, 0.75, 0.5, 0x475569);
  stand.position.set(x, 0.38, z);
  g.add(stand);
  const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.045, 12, 28), mat(0x1e293b, { metalness: 0.35 }));
  wheel.rotation.x = Math.PI / 2;
  wheel.position.set(x, 0.92, z);
  g.add(wheel);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.06, 12), mat(0x94a3b8, { metalness: 0.5 }));
  hub.rotation.x = Math.PI / 2;
  hub.position.set(x, 0.92, z);
  g.add(hub);
  const sign = createZonePin('🎛️');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildRouteWall() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.routeWall;
  if (!placeAsset('bookcase', x - 0.55, z, Math.PI)) {
    const wall = box(2.4, 1.15, 0.1, 0xf1f5f9, { flat: true });
    wall.position.set(x, 1.1, z);
    g.add(wall);
  }
  placeAsset('monitor', x + 0.55, z, 0, 0.85);
  const screenMat = new THREE.MeshStandardMaterial({
    map: createScreenTexture('route'),
    emissive: 0x4ecdc4,
    emissiveIntensity: 0.12,
  });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.35, 0.82), screenMat);
  screen.position.set(x + 0.55, 1.08, z + 0.22);
  g.add(screen);
  sceneRefs.routeWallMat = screenMat;
  const sign = createZonePin('📈');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildSecocStation() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.secoc;
  placeAsset('bookcase', x + 0.55, z, Math.PI);
  placeAsset('monitor', x - 0.45, z, 0, 0.8);
  const lock = box(0.22, 0.28, 0.06, 0xfbbf24, { emissive: 0xfbbf24, emissiveIntensity: 0.25 });
  lock.position.set(x + 0.55, 0.95, z + 0.24);
  g.add(lock);
  const panda = box(0.55, 0.12, 0.85, 0x0f172a, { metalness: 0.35 });
  panda.position.set(x - 0.45, 0.52, z);
  g.add(panda);
  const sign = createZonePin('🔐');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildAdaptShelf() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.adapt;
  const shelf = box(1.6, 0.9, 0.35, 0xcbd5e1);
  shelf.position.set(x, 0.45, z);
  g.add(shelf);
  for (let i = 0; i < 4; i += 1) {
    const binder = box(0.22, 0.28, 0.08, [0x60a5fa, 0x4ecdc4, 0xf472b6, 0xfbbf24][i], { flat: true });
    binder.position.set(x - 0.45 + i * 0.28, 0.72, z + 0.12);
    g.add(binder);
  }
  const sign = createZonePin('🔧');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildCiStrip() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.ci;
  const board = box(1.4, 0.55, 0.08, 0x0f172a);
  board.position.set(x, 1.35, z);
  g.add(board);
  sceneRefs.ciLights = [];
  for (let i = 0; i < 5; i += 1) {
    const led = new THREE.Mesh(
      new THREE.SphereGeometry(0.06, 8, 8),
      mat(i % 2 ? 0x4ade80 : 0x38bdf8, { emissive: i % 2 ? 0x4ade80 : 0x38bdf8, emissiveIntensity: 0.5 }),
    );
    led.position.set(x - 0.48 + i * 0.24, 1.35, z + 0.06);
    g.add(led);
    sceneRefs.ciLights.push(led);
  }
  placeAsset('streetLight', x - 0.85, z - 0.55, 0);
  placeAsset('streetLight', x + 0.85, z - 0.55, Math.PI);
  const sign = createZonePin('⚙️');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildCloudAntenna() {
  const g = new THREE.Group();
  const { x, z } = ZONE_POIS.cloud;
  const pole = box(0.08, 1.4, 0.08, 0x64748b, { metalness: 0.4 });
  pole.position.set(x, 0.7, z);
  g.add(pole);
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.22, 10, 8, 0, Math.PI * 2, 0, Math.PI / 2), mat(0x38bdf8, { metalness: 0.3 }));
  dish.rotation.x = Math.PI;
  dish.position.set(x, 1.35, z);
  g.add(dish);
  const sign = createZonePin('☁️');
  sign.position.set(x, 0, z - 0.55);
  g.add(sign);
  scene.add(g);
}

function buildDrivingTheme() {
  buildObdCorner();
  buildOffroadBay();
  buildEngageGate();
  buildAlertWall();
  buildSteeringStation();
  buildRouteWall();
  buildSecocStation();
  buildAdaptShelf();
  buildCiStrip();
  buildCloudAntenna();
  updateGateFromVehicle();
  refreshAlertPanel();
}

function buildLights() {
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  scene.add(new THREE.HemisphereLight(0xf8fafc, 0x475569, 0.45));
  const sun = new THREE.DirectionalLight(0xffffff, 1.05);
  sun.position.set(10, 18, 12);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 45;
  const s = 12;
  sun.shadow.camera.left = -s;
  sun.shadow.camera.right = s;
  sun.shadow.camera.top = s;
  sun.shadow.camera.bottom = -s;
  sun.shadow.bias = -0.0002;
  scene.add(sun);
}

async function buildOfficeScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1220);
  scene.fog = new THREE.Fog(0x0b1220, 20, 48);

  assetKit = new AssetKit();
  await assetKit.load();

  buildFloor();
  buildWallsAndWindows();
  buildDrivingTheme();
  buildBreakRoom();
  buildLounge();
  buildReplayTrack();

  const deskKeys = new Set();
  for (const ch of characters.values()) {
    const key = `${ch.deskX.toFixed(2)}:${ch.deskZ.toFixed(2)}`;
    if (!deskKeys.has(key)) {
      buildWorkstation(ch.deskX, ch.deskZ, deskKeys.size % 2 === 0 ? 'route' : 'comma');
      deskKeys.add(key);
    }
  }
  if (!deskKeys.size) {
    for (let i = 0; i < 9; i += 1) {
      const slot = deskSlot(i);
      buildWorkstation(slot.x, slot.z, i % 2 === 0 ? 'route' : 'comma');
    }
  }

  buildLights();
  syncAgentRigs();
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
      color: agentColor(id),
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
  ch.color = agentColor(id);
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
    if (!ids.has(id)) {
      characters.delete(id);
      removeAgentRig(id);
    }
  }
}

function applyLiveStatus() {
  const statusMap = new Map();
  for (const a of officeState?.agents || []) statusMap.set(a.id, a);
  let workingTool = '';
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
        workingTool = live.tool || 'tool';
      } else if (next === 'assigned') {
        ch.bubble = '收到任务';
        ch.bubbleT = 2;
        ch.targetX = ch.deskX;
        ch.targetZ = ch.deskZ;
      } else if (next === 'idle') ch.tool = '';
    } else if (live.tool && live.tool !== ch.tool) {
      ch.tool = live.tool;
      if (ch.status === 'working') {
        ch.bubble = `🔧 ${live.tool}`;
        ch.bubbleT = 2.5;
        workingTool = live.tool;
      }
    }
  }
  if (workingTool) pulseDeskScreens(workingTool);
}

function pickIdleTarget(ch, t) {
  if (ch.status !== 'idle') return;
  const zoneKey = AGENT_ZONE[ch.id];
  const zone = zoneKey ? ZONE_POIS[zoneKey] : null;
  const cycle = Math.floor(t / 8 + ch.phase) % 5;

  if (zone && ch.behavior !== 'nap') {
    if (cycle < 2) {
      ch.targetX = zone.x;
      ch.targetZ = zone.z;
      return;
    }
  }

  if (ch.id === 'pc' && ch.behavior === 'walk') {
    ch.targetX = cycle % 2 ? ZONE_POIS.replay.x : ch.deskX;
    ch.targetZ = cycle % 2 ? ZONE_POIS.replay.z : ch.deskZ;
    return;
  }
  switch (ch.behavior) {
    case 'coffee':
      ch.targetX = cycle < 2 ? ZONE_POIS.coffee.x : ch.deskX;
      ch.targetZ = cycle < 2 ? ZONE_POIS.coffee.z : ch.deskZ;
      break;
    case 'walk':
      ch.targetX = cycle % 2 ? ZONE_POIS.lounge.x : ch.deskX;
      ch.targetZ = cycle % 2 ? ZONE_POIS.lounge.z : ch.deskZ;
      break;
    default:
      ch.targetX = ch.deskX;
      ch.targetZ = ch.deskZ;
  }
}

function updateCharacter(ch, dt, t) {
  if (ch.bubbleT > 0) ch.bubbleT -= dt;
  if (ch.status === 'idle') pickIdleTarget(ch, t);

  const dx = ch.targetX - ch.x;
  const dz = ch.targetZ - ch.z;
  const dist = Math.hypot(dx, dz);
  const speed = ch.status === 'working' ? 0 : 1.2;
  if (dist > 0.05) {
    const step = Math.min(dist, speed * dt);
    ch.x += (dx / dist) * step;
    ch.z += (dz / dist) * step;
    ch.walkT += dt * 10;
  } else {
    ch.walkT = 0;
  }

  if (ch.status === 'working') ch.y = Math.sin(t * 12 + ch.phase) * 0.03;
  else if (ch.status === 'idle' && ch.behavior === 'nap') ch.y = Math.sin(t * 1.2 + ch.phase) * 0.02;
  else if (ch.walkT > 0) ch.y = Math.abs(Math.sin(ch.walkT)) * 0.05;
  else ch.y = Math.sin(t * 2 + ch.phase) * 0.015;
}

function removeAgentRig(id) {
  const rig = agentRigs.get(id);
  if (!rig) return;
  pickables = pickables.filter((m) => m.userData?.agentId !== id);
  scene?.remove(rig.group);
  agentRigs.delete(id);
}

function syncAgentRigs() {
  for (const ch of characters.values()) {
    if (!agentRigs.has(ch.id)) createAgentRig(ch);
  }
}

function updateAgentVisual(ch, t) {
  const rig = agentRigs.get(ch.id);
  if (!rig) return;

  const walking = ch.walkT > 0;
  rig.group.position.set(ch.x, ch.y, ch.z);
  if (walking) rig.group.rotation.y = Math.atan2(ch.targetX - ch.x, ch.targetZ - ch.z);
  animateRig(rig, ch, walking);

  const active = ch.status !== 'idle';
  const selected = ch.id === selectedId;
  rig.parts.ring.material.color.setHex(
    selected ? 0x4ecdc4 : (active ? (ch.status === 'working' ? 0x4ade80 : 0xfbbf24) : 0x94a3b8),
  );
  rig.parts.ring.material.opacity = selected ? 0.95 : (active ? 0.8 : 0.35);

  let icon = ch.icon;
  if (ch.status === 'idle' && ch.behavior === 'nap' && !walking) icon = '😴';
  if (ch.status === 'idle' && ch.behavior === 'stretch' && !walking) icon = '🧘';

  const statusText = ch.status === 'working' && ch.tool ? ch.tool : (STATUS_LABEL[ch.status] || ch.status);
  const showLabel = selected || active || (ch.bubbleT > 0 && ch.bubble);
  const lines = showLabel
    ? (ch.bubbleT > 0 && ch.bubble && !selected && !active
      ? [ch.bubble]
      : [ch.name, statusText].filter(Boolean))
    : [];
  const labelSig = `${lines.join('|')}|${active}|${selected}|${icon}|${showLabel}`;
  if (rig.labelSig !== labelSig) {
    if (rig.label) {
      rig.group.remove(rig.label);
      rig.label.material?.map?.dispose?.();
      rig.label.material?.dispose?.();
      rig.label = null;
    }
    rig.parts.emoji.material?.map?.dispose?.();
    rig.group.remove(rig.parts.emoji);
    rig.parts.emoji = createEmojiSprite(icon);
    rig.parts.emoji.position.y = 1.02;
    rig.group.add(rig.parts.emoji);
    if (showLabel && lines.length) {
      rig.label = createLabelSprite(lines.slice(0, 2), { active, selected, compact: true });
      rig.group.add(rig.label);
    }
    rig.labelSig = labelSig;
  }
}

function resize() {
  if (!renderer || !camera || !mount) return;
  const rect = mount.getBoundingClientRect();
  const w = Math.max(280, rect.width);
  const h = Math.max(220, rect.height);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  controls?.update();
}

function updateSceneDynamics(dt, t) {
  sceneRefs.flowPhase += dt * (sceneRefs.driving ? 2.8 : 0.6);
  sceneRefs.laneFlow.forEach((stripe, i) => {
    if (!stripe.material) return;
    const pulse = 0.45 + 0.35 * Math.sin(sceneRefs.flowPhase * 2 + i * 0.7);
    stripe.material.opacity = sceneRefs.driving ? Math.min(0.95, pulse + 0.25) : pulse;
    if (sceneRefs.driving) {
      stripe.position.z = 0.3 + Math.sin(sceneRefs.flowPhase + i * 0.4) * 0.08;
    }
  });

  updateGateFromVehicle();

  if (sceneRefs.offroadCar) {
    const driving = sceneRefs.driving;
    sceneRefs.offroadCar.visible = !driving;
    if (!driving) {
      sceneRefs.offroadCar.position.y = Math.sin(t * 1.5) * 0.01;
    }
  }

  sceneRefs.ciLights.forEach((led, i) => {
    const on = (Math.floor(t * 2) + i) % 3 !== 0;
    led.material.emissiveIntensity = on ? 0.55 + Math.sin(t * 4 + i) * 0.2 : 0.08;
  });

  for (const entry of sceneRefs.deskScreens) {
    if (entry.pulseT > 0) {
      entry.pulseT -= dt;
      entry.mat.emissiveIntensity = 0.15 + Math.sin(t * 10) * 0.2;
      if (entry.pulseT <= 0) {
        entry.mat.emissiveIntensity = 0.12;
        entry.mat.emissive.setHex(0x4ecdc4);
      }
    }
  }
}

function renderFrame() {
  if (!renderer || !scene || !camera) return;
  const dt = Math.min(0.05, clock?.getDelta() ?? 0.016);
  const now = performance.now() / 1000;

  updateSceneDynamics(dt, now);

  if (!drivingPaused && !reducedMotion) {
    [...characters.values()].forEach((ch) => updateCharacter(ch, dt, now));
  }
  for (const ch of characters.values()) updateAgentVisual(ch, now);

  controls?.update();
  renderer.render(scene, camera);

  let overlay = mount?.querySelector('.office-driving-overlay');
  if (drivingPaused && mount) {
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'office-driving-overlay';
      mount.appendChild(overlay);
    }
    const vs = sceneRefs.vehicleState || {};
    const alert = vs.alert_text1 || vs.alertText1 || '';
    const speed = vs.vEgoKph ?? (vs.v_ego != null ? Math.round(vs.v_ego * 3.6) : null);
    const op = vs.active ? 'OP 已激活' : (vs.engageable ? '可 Engage' : (vs.enabled ? '待机' : ''));
    const bits = [speed != null ? `${speed} km/h` : '', op, alert].filter(Boolean);
    overlay.innerHTML = `<strong>行驶中 · 专员动画已暂停</strong><span>${bits.join(' · ') || '车道流光联动中'}</span>`;
  } else {
    overlay?.remove();
  }
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
  renderFrame();
  rafId = requestAnimationFrame(loop);
}

function pickAgentAt(clientX, clientY) {
  if (!renderer || !camera || !raycaster || !pointer) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickables, false);
  return hits[0]?.object?.userData?.agentId || null;
}

function onPointerDown(ev) {
  clickDrag = { x0: ev.clientX, y0: ev.clientY, moved: false };
}

function onPointerMove(ev) {
  if (!clickDrag) return;
  if (Math.hypot(ev.clientX - clickDrag.x0, ev.clientY - clickDrag.y0) > 5) clickDrag.moved = true;
}

function onPointerUp(ev) {
  if (clickDrag && !clickDrag.moved) {
    const id = pickAgentAt(ev.clientX, ev.clientY);
    if (id) {
      selectedId = id;
      onSelectAgent?.(id);
      renderFrame();
    }
  }
  clickDrag = null;
}

function bindEvents() {
  const el = renderer.domElement;
  el.addEventListener('pointerdown', onPointerDown);
  el.addEventListener('pointermove', onPointerMove);
  el.addEventListener('pointerup', onPointerUp);
  el.addEventListener('pointercancel', onPointerUp);
}

function unbindEvents() {
  const el = renderer?.domElement;
  if (!el) return;
  el.removeEventListener('pointerdown', onPointerDown);
  el.removeEventListener('pointermove', onPointerMove);
  el.removeEventListener('pointerup', onPointerUp);
  el.removeEventListener('pointercancel', onPointerUp);
}

function showLoadError(msg) {
  if (!mount) return;
  mount.innerHTML = `<div class="office-scene-error">3D 场景加载失败<br><small>${msg || '请检查 static/vendor/three'}</small></div>`;
}

async function init(el) {
  mount = el || document.getElementById('officeSceneHost');
  if (!mount) return false;

  try {
    reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    mount.innerHTML = '';
    mount.classList.add('office-scene-mount');

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.domElement.className = 'office-scene-gl';
    mount.appendChild(renderer.domElement);

    camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
    camera.position.set(18, 16, 18);

    clock = new THREE.Clock();
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    await buildOfficeScene();

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 9;
    controls.maxDistance = 28;
    controls.maxPolarAngle = Math.PI / 2.15;
    controls.minPolarAngle = Math.PI / 6;
    controls.target.set(0, 0.35, 0.4);
    controls.enablePan = true;
    controls.panSpeed = 0.6;
    controls.rotateSpeed = 0.55;

    bindEvents();
    resize();

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => resize());
      resizeObserver.observe(mount);
    } else {
      window.addEventListener('resize', resize);
    }
    document.addEventListener('visibilitychange', onVisibilityChange);
    return true;
  } catch (e) {
    console.error('OfficeScene init failed', e);
    showLoadError(e?.message);
    return false;
  }
}

function onVisibilityChange() {
  if (!document.hidden && running && !drivingPaused) {
    lastFrameMs = 0;
    renderFrame();
  }
}

function start() {
  if (running || !renderer) return;
  running = true;
  lastFrameMs = 0;
  clock?.getDelta();
  rafId = requestAnimationFrame(loop);
}

function stop() {
  running = false;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = 0;
}

function destroy() {
  stop();
  unbindEvents();
  controls?.dispose();
  controls = null;
  resizeObserver?.disconnect();
  resizeObserver = null;
  window.removeEventListener('resize', resize);
  document.removeEventListener('visibilitychange', onVisibilityChange);
  renderer?.dispose();
  renderer?.domElement?.remove();
  renderer = null;
  scene = null;
  camera = null;
  characters.clear();
  agentRigs.clear();
  pickables = [];
  mount = null;
  assetKit = null;
}

function setDrivingPaused(paused) {
  drivingPaused = !!paused;
  sceneRefs.driving = !!paused;
  if (running && renderer) {
    lastFrameMs = 0;
    renderFrame();
  }
}

function setVehicleState(vs) {
  sceneRefs.vehicleState = vs && typeof vs === 'object' ? { ...vs } : null;
  refreshAlertPanel();
  updateGateFromVehicle();
  if (running && renderer) renderFrame();
}

function setAgents(list) {
  syncAgents(list);
  if (scene) syncAgentRigs();
}

function applyOffice(data) {
  officeState = data || null;
  applyLiveStatus();
}

function setSelectedAgent(id) {
  selectedId = id || null;
  if (running && renderer) renderFrame();
}

function setOnSelectAgent(fn) {
  onSelectAgent = typeof fn === 'function' ? fn : null;
}

export const OfficeScene = {
  init,
  destroy,
  start,
  stop,
  resize,
  setAgents,
  applyOffice,
  setDrivingPaused,
  setVehicleState,
  setSelectedAgent,
  setOnSelectAgent,
};

if (typeof window !== 'undefined') {
  window.OfficeScene = OfficeScene;
}
