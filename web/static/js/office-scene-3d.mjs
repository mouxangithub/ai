/**
 * OP 办公室 — Three.js 完整 3D（OrbitControls + GLTF + 动画角色）
 */
import * as THREE from '/static/vendor/three/three.module.js';
import { OrbitControls } from '/static/vendor/three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from '/static/vendor/three/examples/jsm/loaders/GLTFLoader.js';

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

const POIs = {
  coffee: { x: -5.2, z: 4.2 },
  lounge: { x: 5.4, z: 4.0 },
  treadmill: { x: 5.8, z: -2.2 },
  door: { x: 0, z: -5.0 },
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
    this.loader = new GLTFLoader();
  }

  async load() {
    let manifest = { models: {} };
    try {
      const res = await fetch('/static/vendor/office/manifest.json');
      if (res.ok) manifest = await res.json();
    } catch { /* procedural only */ }

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

function createEmojiSprite(emoji) {
  const size = 128;
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
  sprite.scale.set(0.72, 0.72, 1);
  sprite.renderOrder = 10;
  return sprite;
}

function createLabelSprite(lines, { active = false, selected = false } = {}) {
  const padY = 8;
  const lineH = 18;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const width = 220;
  const height = padY * 2 + lineH * lines.length;
  canvas.width = width;
  canvas.height = height;
  ctx.fillStyle = selected
    ? 'rgba(78, 205, 196, 0.22)'
    : (active ? 'rgba(74, 222, 128, 0.16)' : 'rgba(15, 23, 42, 0.82)');
  ctx.strokeStyle = selected
    ? 'rgba(78, 205, 196, 0.9)'
    : (active ? 'rgba(74, 222, 128, 0.65)' : 'rgba(148, 163, 184, 0.45)');
  ctx.lineWidth = 2;
  roundRect(ctx, 1, 1, width - 2, height - 2, 10);
  ctx.fill();
  ctx.stroke();
  ctx.textAlign = 'center';
  lines.forEach((line, i) => {
    const y = padY + lineH * i + lineH * 0.72;
    ctx.font = i === 0 ? '600 15px system-ui, sans-serif' : '12px system-ui, sans-serif';
    ctx.fillStyle = i === 0 ? '#f1f5f9' : (active ? '#86efac' : '#94a3b8');
    ctx.fillText(line, width / 2, y);
  });
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sprite.scale.set(1.55 * (width / height), 1.55, 1);
  sprite.position.y = 1.55;
  sprite.renderOrder = 11;
  return sprite;
}

function createAreaSign(title, emoji) {
  const canvas = document.createElement('canvas');
  canvas.width = 180;
  canvas.height = 56;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(255,255,255,0.94)';
  roundRect(ctx, 2, 2, 176, 52, 10);
  ctx.fill();
  ctx.font = '22px "Segoe UI Emoji", sans-serif';
  ctx.fillText(emoji, 18, 36);
  ctx.font = '600 15px system-ui, sans-serif';
  ctx.fillStyle = '#334155';
  ctx.fillText(title, 48, 35);
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sprite.scale.set(1.35, 0.42, 1);
  sprite.position.y = 0.05;
  return sprite;
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
  emoji.position.y = 1.08;

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

function proceduralDesk(x, z) {
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

  const monitor = box(0.55, 0.36, 0.05, 0x0f172a, { metalness: 0.25 });
  monitor.position.set(0, 1.05, -0.2);
  g.add(monitor);
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.48, 0.28),
    new THREE.MeshBasicMaterial({ color: 0x4ecdc4, transparent: true, opacity: 0.45 }),
  );
  screen.position.set(0, 1.05, -0.168);
  g.add(screen);
  const stand = box(0.1, 0.14, 0.1, 0x64748b);
  stand.position.set(0, 0.88, -0.2);
  g.add(stand);

  if (assetKit?.clone('chair', x, z + 0.62, Math.PI, 0.45)) {
    /* glb chair */
  } else {
    const seat = box(0.44, 0.08, 0.44, 0x475569);
    seat.position.set(0, 0.44, 0.58);
    g.add(seat);
    const back = box(0.44, 0.45, 0.07, 0x334155);
    back.position.set(0, 0.74, 0.78);
    g.add(back);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.04, 12), mat(0x1e293b));
    base.position.set(0, 0.38, 0.58);
    g.add(base);
  }

  scene.add(g);
}

function buildBreakRoom() {
  const g = new THREE.Group();
  const counter = box(3.0, 0.95, 0.6, 0xffffff, { flat: true });
  counter.position.set(-5.3, 0.48, 4.3);
  g.add(counter);
  const backsplash = box(3.0, 0.55, 0.06, 0xe2e8f0);
  backsplash.position.set(-5.3, 1.15, 4.05);
  g.add(backsplash);
  const machine = box(0.5, 0.6, 0.38, 0x1e293b, { metalness: 0.35 });
  machine.position.set(-6.1, 1.05, 4.15);
  g.add(machine);
  for (let i = 0; i < 4; i += 1) {
    const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.035, 0.1, 10), mat(0xf1f5f9));
    cup.position.set(-5.1 + i * 0.16, 1.0, 4.12);
    g.add(cup);
  }
  const sign = createAreaSign('茶水间', '☕');
  sign.position.set(-5.2, 0, 5.1);
  g.add(sign);
  scene.add(g);
}

function buildLounge() {
  const g = new THREE.Group();
  if (!assetKit?.clone('sofa', 5.4, 4.1, Math.PI, 1)) {
    const sofa = box(2.0, 0.45, 0.78, 0xe2e8f0, { flat: true });
    sofa.position.set(5.4, 0.28, 4.1);
    g.add(sofa);
    const back = box(2.0, 0.58, 0.15, 0xcbd5e1);
    back.position.set(5.4, 0.66, 3.72);
    g.add(back);
  }
  const table = box(0.6, 0.3, 0.6, 0xffffff, { flat: true });
  table.position.set(4.5, 0.15, 4.55);
  g.add(table);
  if (!assetKit?.clone('plant', 6.2, 3.5, 0, 0.8)) {
    const pot = box(0.24, 0.2, 0.24, 0x78350f);
    pot.position.set(6.2, 0.1, 3.5);
    g.add(pot);
    const plant = new THREE.Mesh(new THREE.SphereGeometry(0.24, 10, 10), mat(0x22c55e, { flat: true }));
    plant.position.set(6.2, 0.4, 3.5);
    g.add(plant);
  }
  const sign = createAreaSign('休息区', '🛋');
  sign.position.set(5.4, 0, 5.1);
  g.add(sign);
  scene.add(g);
}

function buildTreadmill() {
  const g = new THREE.Group();
  const { x, z } = POIs.treadmill;
  const base = box(1.3, 0.2, 2.3, 0x334155, { metalness: 0.2 });
  base.position.set(x, 0.14, z);
  g.add(base);
  const belt = box(0.95, 0.05, 1.75, 0x111827);
  belt.position.set(x, 0.28, z);
  g.add(belt);
  [-0.5, 0.5].forEach((ox) => {
    const rail = box(0.07, 0.85, 1.65, 0x94a3b8, { metalness: 0.45 });
    rail.position.set(x + ox, 0.62, z);
    g.add(rail);
  });
  const sign = createAreaSign('联调区', '🏃');
  sign.position.set(x, 0, z - 1.55);
  g.add(sign);
  scene.add(g);
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
  sign.position.set(0, 0, -hh + 0.55);
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
    new THREE.PlaneGeometry(ROOM.floorW, ROOM.floorH),
    mat(0xe8edf3, { roughness: 0.95 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const rug = new THREE.Mesh(new THREE.PlaneGeometry(8, 6), mat(0xdbe4ee, { roughness: 1 }));
  rug.rotation.x = -Math.PI / 2;
  rug.position.set(0, 0.01, 0.5);
  scene.add(rug);

  const grid = new THREE.GridHelper(ROOM.floorW, 14, 0xc7d2de, 0xd8e0ea);
  grid.position.y = 0.015;
  grid.material.transparent = true;
  grid.material.opacity = 0.4;
  scene.add(grid);
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
  buildBreakRoom();
  buildLounge();
  buildTreadmill();

  const deskKeys = new Set();
  for (const ch of characters.values()) {
    const key = `${ch.deskX.toFixed(2)}:${ch.deskZ.toFixed(2)}`;
    if (!deskKeys.has(key)) {
      if (!assetKit.clone('desk', ch.deskX, ch.deskZ, 0, 1)) {
        proceduralDesk(ch.deskX, ch.deskZ);
      }
      deskKeys.add(key);
    }
  }
  if (!deskKeys.size) {
    for (let i = 0; i < 9; i += 1) {
      const slot = deskSlot(i);
      proceduralDesk(slot.x, slot.z);
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
      } else if (next === 'idle') ch.tool = '';
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
  if (ch.id === 'pc' && ch.behavior === 'walk') {
    ch.targetX = cycle % 2 ? POIs.treadmill.x : ch.deskX;
    ch.targetZ = cycle % 2 ? POIs.treadmill.z : ch.deskZ;
    return;
  }
  switch (ch.behavior) {
    case 'coffee':
      ch.targetX = cycle < 2 ? POIs.coffee.x : ch.deskX;
      ch.targetZ = cycle < 2 ? POIs.coffee.z : ch.deskZ;
      break;
    case 'walk':
      ch.targetX = cycle % 2 ? POIs.lounge.x : ch.deskX;
      ch.targetZ = cycle % 2 ? POIs.lounge.z : ch.deskZ;
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
  const lines = [ch.name, statusText];
  if (ch.bubbleT > 0 && ch.bubble) lines.push(ch.bubble);
  const labelSig = `${lines.join('|')}|${active}|${selected}|${icon}`;
  if (rig.labelSig !== labelSig) {
    if (rig.label) {
      rig.group.remove(rig.label);
      rig.label.material?.map?.dispose?.();
      rig.label.material?.dispose?.();
    }
    rig.parts.emoji.material?.map?.dispose?.();
    rig.group.remove(rig.parts.emoji);
    rig.parts.emoji = createEmojiSprite(icon);
    rig.parts.emoji.position.y = 1.08;
    rig.group.add(rig.parts.emoji);
    rig.label = createLabelSprite(lines.slice(0, 3), { active, selected });
    rig.group.add(rig.label);
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

function renderFrame() {
  if (!renderer || !scene || !camera) return;
  const dt = Math.min(0.05, clock?.getDelta() ?? 0.016);
  const now = performance.now() / 1000;

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
      overlay.innerHTML = '<strong>行驶中 · 办公室动画已暂停</strong><span>不影响辅助驾驶</span>';
      mount.appendChild(overlay);
    }
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

    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 120);
    camera.position.set(14, 13, 14);

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
    controls.target.set(0, 0.45, 0.5);
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
  if (running && renderer) {
    lastFrameMs = 0;
    renderFrame();
  }
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
  setSelectedAgent,
  setOnSelectAgent,
};

if (typeof window !== 'undefined') {
  window.OfficeScene = OfficeScene;
}
