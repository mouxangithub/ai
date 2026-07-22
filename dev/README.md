# PC 本地预览

在 Windows / macOS / Linux 开发机上快速启动 Web UI（无需 AGNOS 编译环境）。

## 启动

在 openpilot 根目录执行：

```bash
py -3 ai/dev/run_pc.py
# 或指定端口
py -3 ai/dev/run_pc.py --port 5090 --host 127.0.0.1
```

浏览器打开：**http://127.0.0.1:5090/**

## 限制

| 项 | PC 预览 | 车机 AGNOS |
|----|---------|------------|
| Params | Mock 内存字典 | 真实 `/data/params` |
| 车辆状态 | 无 cereal，状态为离线默认值 | 实时 vEgo / 点火等 |
| Web 终端 PTY | Windows 不可用（提示用 WSL） | bash PTY |
| TSK / SecOC | 缺 `pycryptodome` 时自动跳过 | 完整 |
| 聊天 / 设置 / Canvas | 可用（需配置 API Key） | 完整 |

## 依赖

```bash
pip install aiohttp
# 可选：pip install pycryptodome  # 启用 TSK 路由
```

## 车机正式运行

```bash
cd /data/openpilot
./ai/aid.py --port 5090
```

或由 manager 拉起（见安装脚本 `ai/install/install.sh`）。
