# Dragonpilot 调优预设（dp_*）

## 工具

- `list_tune_presets` — comfort_follow、alka_enable、vag_eps_safe 等  
- `apply_tune_preset` — 应用 DP 预设  
- `rollback_last_tune` — 恢复快照  

sunnypilot 预设见 **sp-tune-presets** / `list_sp_tune_presets`。

## 注意

本 sunnypilot fork **可能无** `dp_*` params_keys；预设仅在安装了 dragonpilot 或 Params 中存在对应键时有效。失败时用 `diff_params` 检查。
