# 前端 vendor 依赖（离线可用）

与 xterm 相同：**全部随仓库提交**，车机无网也能用，安装脚本不再拉 CDN。

## Three.js（OP 办公室 3D）

已内置在仓库（`three@0.160.1`）：

| 文件 | 说明 |
|------|------|
| `three/three.module.js` | ES Module 主库（办公室场景使用） |
| `three/three.min.js` | UMD 备用 |
| `three/examples/jsm/loaders/GLTFLoader.js` | GLB 家具 |
| `three/examples/jsm/controls/OrbitControls.js` | 旋转/缩放视角 |

**维护者升级版本**（需联网，在开发机执行后提交 git）：

```bash
VER=0.160.1
BASE=ai/web/static/vendor/three
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/build/three.module.js" -o "$BASE/three.module.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/build/three.min.js" -o "$BASE/three.min.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/examples/jsm/loaders/GLTFLoader.js" -o "$BASE/examples/jsm/loaders/GLTFLoader.js"
curl -fsSL "https://cdn.jsdelivr.net/npm/three@${VER}/examples/jsm/controls/OrbitControls.js" -o "$BASE/examples/jsm/controls/OrbitControls.js"
```

## 办公室 GLB（可选）

`office/manifest.json` 列出可选家具模型。默认用程序化几何体，不依赖 GLB。

若要 Kenney CC0 家具：手动将 `desk.glb` 等放入 `office/`，或开发机运行：

```bash
node ai/scripts/fetch_office_assets.mjs
```

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
