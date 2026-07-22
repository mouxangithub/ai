# 前端 vendor 依赖（离线可用）

避免依赖 jsDelivr 等 CDN，车机无网或 CDN 被墙时仍可加载 Web UI。

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

引用见 `index.html` → `/static/vendor/xterm/...`
