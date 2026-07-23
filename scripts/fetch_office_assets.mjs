#!/usr/bin/env node
/**
 * Download CC0 office GLB assets into ai/web/static/vendor/office/
 * Run: node ai/scripts/fetch_office_assets.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, '../web/static/vendor/office');

/** Public mirrors / samples — all CC0 or Khronos sample (replace via poly.pizza if needed). */
const ASSETS = [
  {
    name: 'chair.glb',
    urls: [
      'https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@master/2.0/Chair/glTF-Binary/Chair.glb',
    ],
  },
  {
    name: 'plant.glb',
    urls: [
      'https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@master/2.0/PottedPlant/glTF-Binary/PottedPlant.glb',
    ],
  },
];

async function fetchOne(url) {
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return Buffer.from(await res.arrayBuffer());
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  let ok = 0;
  for (const asset of ASSETS) {
    const dest = path.join(OUT, asset.name);
    if (fs.existsSync(dest) && fs.statSync(dest).size > 1000) {
      console.log(`skip ${asset.name} (exists)`);
      ok += 1;
      continue;
    }
    let saved = false;
    for (const url of asset.urls) {
      try {
        console.log(`fetch ${asset.name} <- ${url}`);
        const buf = await fetchOne(url);
        fs.writeFileSync(dest, buf);
        console.log(`  wrote ${buf.length} bytes`);
        ok += 1;
        saved = true;
        break;
      } catch (e) {
        console.warn(`  failed: ${e.message}`);
      }
    }
    if (!saved) console.warn(`! could not fetch ${asset.name}`);
  }
  console.log(`\nDone: ${ok}/${ASSETS.length} models in ${OUT}`);
  console.log('Tip: add desk.glb / sofa.glb from https://kenney.nl/assets/furniture-kit (CC0) for best look.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
