# 前端 vendor 依赖（离线可用）

与 xterm 相同：**全部随仓库提交**，车机无网也能用，安装脚本不再拉 CDN。

## Three.js（OP 办公室 3D）

已内置在仓库（`three@0.160.1`）：

| 文件 | 说明 |
|------|------|
| `three/three.module.js` | ES Module 主库（办公室场景使用） |
| `three/three.min.js` | UMD 备用 |
| `three/examples/jsm/loaders/GLTFLoader.js` | GLB 家具（可选） |
| `three/examples/jsm/utils/BufferGeometryUtils.js` | GLTFLoader 依赖 |
| `three/examples/jsm/controls/OrbitControls.js` | 旋转/缩放视角 |

**维护者升级版本**（需联网，在开发机执行后提交 git）：

```bash
VER=0.160.1
BASE=ai/web/static/vendor/three
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/build/three.module.js" -o "$BASE/three.module.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/build/three.min.js" -o "$BASE/three.min.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/examples/jsm/loaders/GLTFLoader.js" -o "$BASE/examples/jsm/loaders/GLTFLoader.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/examples/jsm/utils/BufferGeometryUtils.js" -o "$BASE/examples/jsm/utils/BufferGeometryUtils.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/examples/jsm/controls/OrbitControls.js" -o "$BASE/examples/jsm/controls/OrbitControls.js"
```

## 办公室 GLB（Kenney CC0）

`office/manifest.json` v3 列出 **家具 / 道路 / 赛车** 三套 Kenney 模型（已随仓库提交）。场景在 `office-scene-3d.mjs` 中优先加载 GLB，失败时回退程序化几何体。

| 套件 | 用途 |
|------|------|
| furniture-kit | 工位（桌/椅/显示器）、茶水间、休息区、书柜 |
| city-kit-roads | 中心车道、十字路口、路障、锥桶、路灯 |
| racing-kit | Replay 跑道、赛车、旗子、红绿灯（Engage 区） |

**从 Kenney 官网重新导入**（开发机执行后提交 git）：

```bash
# 1. 将三个 zip 解压到 _staging
#    ai/web/static/vendor/office/_staging/{furniture,roads,racing}
# 2. 复制精选 GLB 到 office/
node ai/scripts/import_kenney_office.mjs
```

许可文件：`office/LICENSE-furniture.txt`、`LICENSE-roads.txt`、`LICENSE-racing.txt`

暂存目录 `_staging/` 仅本地解压用，不必提交。

## xterm（Web 终端）

| 文件 | 来源 |
|------|------|
| `xterm/xterm.js` | @xterm/xterm@5.5.0 |
| `xterm/xterm.css` | @xterm/xterm@5.5.0 |
| `xterm/addon-fit.js` | @xterm/addon-fit@0.10.0 |

更新：

```bash
cd ai/web/static/vendor/xterm
npm pack @xterm/xterm@5.5.0 @xterm/addon-fit@0.10.0
tar -xzf xterm-xterm-5.5.0.tgz && cp package/lib/xterm.js package/css/xterm.css .
tar -xzf xterm-addon-fit-0.10.0.tgz && cp package/lib/addon-fit.js .
rm -rf package *.tgz
```

引用见 `index.html` → `/static/vendor/...`
