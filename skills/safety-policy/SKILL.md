# 安全边界

## 只读（行车中）

- `get_vehicle_state`、`read_params`、`trip_review`、路线/CAN 分析
- 禁止写入 Params、切换模型/车型、重启服务

## 可写（静止 + offroad）

- `write_params`、`apply_*_preset`、`set_mads_settings` 等分组写入工具
- 写入前：`diff_params` 预览 + `save_tune_snapshot`

## 禁止

- SecOC 密钥明文写入（用 TSK 工具）
- `ai_api_key` 等 redacted 键
