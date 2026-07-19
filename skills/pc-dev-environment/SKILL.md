# PC 开发联调

`get_host_environment`、`pc_launch_replay`、`pc_launch_plotjuggler`、`git_*`、`run_scons_build`

## C3 / Panda 开发

- 编译 F4 固件：`build_panda_firmware` 或 `scons` in `panda/board`
- 列出 USB Panda：`list_f4_pandas`
- 刷机文档：`ai/docs/PANDA_FLASH.md`；技能 `c3-dos-panda`
- 车机刷机：`pc_devsync_run` 同步代码后 SSH 跑 `tools/recover_dos_panda.py`

