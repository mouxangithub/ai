#!/usr/bin/env python3
"""Apply Chinese translations to app_zh-CHS.po and app_zh-CHT.po."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS = ROOT / "selfdrive/ui/translations"

# Simplified Chinese translations (msgid -> msgstr)
ZH_CHS = {
  "Firehose": "洪流",
  "Firehose Mode": "洪流模式",
  "🔥 Firehose Mode 🔥": "🔥 洪流模式 🔥",
  "sunnypilot learns to drive by watching humans, like you, drive.\n\nFirehose Mode allows you to maximize your training data uploads to improve openpilot's driving models. More data means bigger models, which means better Experimental Mode.":
    "sunnypilot 通过观察像您这样的真人驾驶来学习驾驶。\n\n"
    "洪流模式可最大化训练数据上传，以改进 openpilot 驾驶模型。数据越多，模型越大，实验模式效果越好。",
  "For maximum effectiveness, bring your device inside and connect to a good USB-C adapter and Wi-Fi weekly.\n\nFirehose Mode can also work while you're driving if connected to a hotspot or unlimited SIM card.\n\n\nFrequently Asked Questions\n\nDoes it matter how or where I drive? Nope, just drive as you normally would.\n\nDo all of my segments get pulled in Firehose Mode? No, we selectively pull a subset of your segments.\n\nWhat's a good USB-C adapter? Any fast phone or laptop charger should be fine.\n\nDoes it matter which software I run? Yes, only upstream openpilot (and particular forks) are able to be used for training.":
    "为获得最佳效果，请每周将设备带回室内，并连接优质 USB-C 充电器与 Wi-Fi。\n\n"
    "若连接热点或不限流量 SIM 卡，驾驶时也可使用洪流模式。\n\n\n"
    "常见问题\n\n"
    "驾驶方式或地点重要吗？不重要，正常驾驶即可。\n\n"
    "洪流模式会拉取我的全部片段吗？不会，我们只会选择性拉取部分片段。\n\n"
    "什么样的 USB-C 充电器合适？任何快充手机或笔记本充电器均可。\n\n"
    "使用什么软件重要吗？是的，仅上游 openpilot（及特定分支）可用于训练。",
  "Do all of my segments get pulled in Firehose Mode?": "洪流模式会拉取我的全部片段吗？",
  "Toggle visibility of advanced sunnypilot controls.<br>This only changes the visibility of the toggles; it does not change the actual enabled/disabled state.":
    "切换高级 sunnypilot 控制项的显示。<br>仅改变开关可见性，不会改变实际启用/禁用状态。",
  "Show Advanced Controls": "显示高级控制项",
  "A beautiful rainbow effect on the path the model wants to take. It does not affect driving in any way.":
    "在模型规划路径上显示彩虹效果，纯视觉装饰，不影响驾驶。",
  "sunnypilot will allow some Toyota/Lexus cars to auto resume during stop and go traffic. This feature is only applicable to certain models that are able to use longitudinal control. This is an alpha feature. Use at your own risk.":
    "sunnypilot 允许部分丰田/雷克萨斯车型在走走停停路况下自动恢复行驶。"
    "此功能仅适用于支持纵向控制的特定车型。此为 Alpha 功能，使用风险自负。",
  "Start the vehicle to check vehicle compatibility.": "启动车辆以检查车辆兼容性。",
  "Stop and Go Hack (Alpha)": "走走停停破解 (Alpha)",
  "Longitudinal Maneuver Mode": "纵向演习模式",
  "Lateral Maneuver Mode": "横向演习模式",
  "UI Debug Mode": "界面调试模式",
  "Enabling this will display warnings when a vehicle is detected in your blind spot as long as your car has BSM supported.":
    "若车辆支持盲点监测 (BSM)，当盲点检测到车辆时将显示警告。",
  "Displays the name of the road the car is traveling on.<br>The OpenStreetMap database of the location must be downloaded from the OSM panel to fetch the road name.":
    "显示车辆当前行驶道路名称。<br>需先在开放街图面板下载该位置的 OpenStreetMap 数据库。",
  "Display useful metrics below the chevron that tracks the lead car only applicable to cars with sunnypilot longitudinal control.":
    "在前车追踪箭头下方显示有用指标，仅适用于启用 sunnypilot 纵向控制的车辆。",
  "When enabled, sunnypilot will attempt to manage the built-in cruise control buttons by emulating button presses for limited longitudinal control.":
    "启用后，sunnypilot 将通过模拟按键来管理原车巡航控制按钮，实现有限的纵向控制。",
  "Enable the beloved MADS feature. Disable toggle to revert back to stock sunnypilot engagement/disengagement.":
    "启用 MADS 功能。关闭开关可恢复默认 sunnypilot 接合/脱离行为。",
  "copyparty is a very capable file server, you can use it to download your routes, view your logs and even make some edits on some files from your browser. Requires you to connect to your comma locally via its IP address.":
    "copyparty 是功能强大的文件服务器，可通过浏览器下载路线、查看日志并编辑部分文件。需通过 IP 地址在本地连接设备。",
  "When toggled on, this creates a prebuilt file to allow accelerated boot times. When toggled off, it removes the prebuilt file so compilation of locally edited cpp files can be made.":
    "开启后创建预编译文件以加快启动；关闭后删除预编译文件，以便编译本地修改的 C++ 文件。",
  "Quickboot mode requires updates to be disabled.<br>Enable 'Disable Updates' in the Software panel first.":
    "快速启动模式需先禁用更新。<br>请先在软件面板中启用「禁用更新」。",
  "Set a timer to delay the auto lane change operation when the blinker is used. No nudge on the steering wheel is required to auto lane change if a timer is set. Default is Nudge.<br>Please use caution when using this feature. Only use the blinker when traffic and road conditions permit.":
    "使用转向灯时设置延迟计时器以延迟自动变道。设置计时器后无需轻推方向盘即可变道，默认为轻推。<br>请谨慎使用，仅在交通和路况允许时使用转向灯。",
  "Toggle to enable a delay timer for seamless lane changes when blind spot monitoring (BSM) detects a obstructing vehicle, ensuring safe maneuvering.":
    "当盲点监测 (BSM) 检测到障碍车辆时启用延迟计时器，以确保安全变道。",
  "Apply a custom timeout for settings UI.<br>This is the time after which settings UI closes automatically if user is not interacting with the screen.":
    "为设置界面设置自定义超时。<br>用户无操作后，设置界面将自动关闭。",
  "Experimental feature to enable stop and go for Subaru Global models with manual handbrake. Models with electric parking brake should keep this disabled. Thanks to martinl for this implementation!":
    "实验功能：为配备手动手刹的斯巴鲁全球车型启用走走停停。配备电子驻车制动的车型请保持关闭。感谢 martinl 的实现！",
  "Enables self-tune for Torque lateral control for platforms that do not use Torque lateral control by default.":
    "为默认不使用扭矩横向控制的平台启用自学习调参。",
  "Less strict settings when using Self-Tune. This allows torqued to be more forgiving when learning values.":
    "自学习时使用较宽松设置，使 torqued 在学习参数时更宽容。",
  "Enables custom tuning for Torque lateral control. Modifying Lateral Acceleration Factor and Friction below will override the offline values indicated in the YAML files within \"opendbc/car/torque_data\". The values will also be used live when \"Manual Real-Time Tuning\" toggle is enabled.":
    "启用扭矩横向控制自定义调参。修改下方横向加速度系数和摩擦系数将覆盖 opendbc/car/torque_data 中 YAML 文件的离线值。启用「手动实时调参」时这些值也会实时生效。",
  "Enforces the torque lateral controller to use the fixed values instead of the learned values from Self-Tune. Enabling this toggle overrides Self-Tune values.":
    "强制扭矩横向控制器使用固定值而非自学习值。启用此开关将覆盖自学习参数。",
  "An alpha version of sunnypilot longitudinal control can be tested, along with Experimental mode, on non-release branches.":
    "在非发布分支上可测试 sunnypilot 纵向控制 Alpha 版及实验模式。",
  "sunnypilot is continuously calibrating, resetting is rarely required. Resetting calibration will restart sunnypilot if the car is powered on.":
    "sunnypilot 会持续校准，通常无需重置。若车辆通电，重置校准将重启 sunnypilot。",
  "A chime and on-screen alert will play when the traffic light you are waiting for turns green and you have no vehicle in front of you.<br>Note: This chime is only designed as a notification. It is the driver's responsibility to observe their environment and make decisions accordingly.":
    "等待的红灯变绿且前方无车时，将播放提示音并显示屏幕警报。<br>注意：此提示音仅为通知，观察环境并做出判断仍是驾驶员的责任。",
  "A chime and on-screen alert will play when you are stopped, and the vehicle in front of you start moving.<br>Note: This chime is only designed as a notification. It is the driver's responsibility to observe their environment and make decisions accordingly.":
    "停车时前方车辆起步，将播放提示音并显示屏幕警报。<br>注意：此提示音仅为通知，观察环境并做出判断仍是驾驶员的责任。",
  "Show an indicator on the left side of the screen to display real-time vehicle acceleration and deceleration. This displays what the car is currently doing, not what the planner is requesting.":
    "在屏幕左侧显示实时加减速指示条，反映车辆当前实际加减速，而非规划器请求值。",
  # Offroad alerts (alerts_offroad.json)
  "Device temperature too high. System cooling down before starting. Current internal component temperature: %1":
    "设备温度过高。系统正在降温，完成后才能启动。当前内部组件温度：%1",
  "Immediately connect to the internet to check for updates. If you do not connect to the internet, sunnypilot won't engage in %1":
    "请立即连接互联网以检查更新。若不连接互联网，sunnypilot 将在 %1 后无法激活",
  "Connect to internet to check for updates. sunnypilot won't automatically start until it connects to internet to check for updates.":
    "请连接互联网以检查更新。sunnypilot 在连接互联网检查更新之前不会自动启动。",
  "Unable to download updates\n%1": "无法下载更新\n%1",
  "Taking camera snapshots. System won't start until finished.":
    "正在拍摄摄像头快照。完成前系统将不会启动。",
  "An update to your device's operating system is downloading in the background. You will be prompted to update when it's ready to install.":
    "设备操作系统更新正在后台下载。准备就绪后将提示您安装。",
  "Failed to register with comma.ai backend. It will not connect or upload to comma.ai servers, and receives no support from comma.ai. If this is a device purchased at comma.ai/shop, open a ticket at https://comma.ai/support.":
    "无法向 comma.ai 后端注册。设备不会连接或上传到 comma.ai 服务器，也不享有 comma.ai 支持。若从 comma.ai/shop 购买，请在 https://comma.ai/support 提交工单。",
  "sunnypilot was unable to identify your car. Your car is either unsupported or its ECUs are not recognized. Please submit a pull request to add the firmware versions to the proper vehicle. Need help? Join discord.comma.ai.":
    "sunnypilot 无法识别您的车辆。您的车辆可能不受支持，或 ECU 未被识别。请提交拉取请求添加固件版本。需要帮助？加入 discord.comma.ai。",
  "sunnypilot detected a change in the device's mounting position. Ensure the device is fully seated in the mount and the mount is firmly secured to the windshield.":
    "sunnypilot 检测到设备安装位置发生变化。请确保设备完全安装在支架中，且支架牢固固定在挡风玻璃上。",
  "OpenStreetMap database is out of date. New maps must be downloaded if you wish to continue using OpenStreetMap data for Enhanced Speed Control and road name display.\n\n%1":
    "OpenStreetMap 数据库已过期。若需继续使用开放街图数据进行增强速度控制和道路名称显示，必须下载新地图。\n\n%1",
  "Poor visibility detected for driver monitoring. Ensure the device has a clear view of the driver. This can be checked in the device settings. Extreme lighting conditions and/or unconventional mounting positions may also trigger this alert.":
    "驾驶员监控能见度不佳。请确保设备能清楚看到驾驶员。可在设备设置中检查。极端光照和/或非传统安装位置也可能触发此警报。",
  "Excessive %1 actuation detected on your last drive. Please contact support at https://comma.ai/support and share your device's Dongle ID for troubleshooting.":
    "检测到上次驾驶中 %1 过度操控。请联系 https://comma.ai/support 支持并提供设备 Dongle ID 以进行故障排除。",
  "<b>Unsupported branch detected</b> - The current version of <b><u>%1</u></b> branch is no longer supported on the comma three. Please go to <b>[Device > Software]</b> and install a supported branch with <b><u>-tici</u></b> in the branch name for the comma three.":
    "<b>检测到不受支持的分支</b> - 当前 <b><u>%1</u></b> 分支版本已不再支持 comma three。请前往 <b>[设备 > 软件]</b> 安装分支名称包含 <b><u>-tici</u></b> 的受支持分支。",
  "longitudinal": "纵向",
  "lateral": "横向",
  "This alert will be cleared when new maps are downloaded.":
    "下载新地图后此警报将清除。",
}

# Traditional Chinese - convert key terms
ZH_CHT = {k: v.replace("软件", "軟體").replace("设置", "設定").replace("启用", "啟用")
          .replace("禁用", "停用").replace("车辆", "車輛").replace("驾驶", "駕駛")
          .replace("纵向", "縱向").replace("横向", "橫向").replace("实验", "實驗")
          .replace("显示", "顯示").replace("启动", "啟動").replace("关闭", "關閉")
          .replace("连接", "連線").replace("训练", "訓練").replace("模型", "模型")
          .replace("片段", "片段").replace("充电器", "充電器").replace("驾驶", "駕駛")
          for k, v in ZH_CHS.items()}

# Manual CHT overrides for better quality
ZH_CHT.update({
  "Firehose": "洪流",
  "Firehose Mode": "洪流模式",
  "Show Advanced Controls": "顯示進階控制項",
  "Longitudinal Maneuver Mode": "縱向演習模式",
  "Lateral Maneuver Mode": "橫向演習模式",
  "Stop and Go Hack (Alpha)": "走走停停破解 (Alpha)",
  "A beautiful rainbow effect on the path the model wants to take. It does not affect driving in any way.":
    "在模型規劃路徑上顯示彩虹效果，純視覺裝飾，不影響駕駛。",
  "longitudinal": "縱向",
  "lateral": "橫向",
  "This alert will be cleared when new maps are downloaded.":
    "下載新地圖後此警報將清除。",
  "Device temperature too high. System cooling down before starting. Current internal component temperature: %1":
    "設備溫度過高。系統正在降溫，完成後才能啟動。當前內部組件溫度：%1",
  "Immediately connect to the internet to check for updates. If you do not connect to the internet, sunnypilot won't engage in %1":
    "請立即連線網際網路以檢查更新。若不連線網際網路，sunnypilot 將在 %1 後無法啟用",
  "Connect to internet to check for updates. sunnypilot won't automatically start until it connects to internet to check for updates.":
    "請連線網際網路以檢查更新。sunnypilot 在連線網際網路檢查更新之前不會自動啟動。",
  "Unable to download updates\n%1": "無法下載更新\n%1",
  "Taking camera snapshots. System won't start until finished.":
    "正在拍攝攝影機快照。完成前系統將不會啟動。",
  "An update to your device's operating system is downloading in the background. You will be prompted to update when it's ready to install.":
    "設備作業系統更新正在背景下載。準備就緒後將提示您安裝。",
  "Failed to register with comma.ai backend. It will not connect or upload to comma.ai servers, and receives no support from comma.ai. If this is a device purchased at comma.ai/shop, open a ticket at https://comma.ai/support.":
    "無法向 comma.ai 後端註冊。設備不會連線或上傳到 comma.ai 伺服器，也不享有 comma.ai 支援。若從 comma.ai/shop 購買，請在 https://comma.ai/support 提交工單。",
  "sunnypilot was unable to identify your car. Your car is either unsupported or its ECUs are not recognized. Please submit a pull request to add the firmware versions to the proper vehicle. Need help? Join discord.comma.ai.":
    "sunnypilot 無法識別您的車輛。您的車輛可能不受支援，或 ECU 未被識別。請提交拉取請求添加韌體版本。需要幫助？加入 discord.comma.ai。",
  "sunnypilot detected a change in the device's mounting position. Ensure the device is fully seated in the mount and the mount is firmly secured to the windshield.":
    "sunnypilot 偵測到設備安裝位置發生變化。請確保設備完全安裝在支架中，且支架牢固固定在擋風玻璃上。",
  "OpenStreetMap database is out of date. New maps must be downloaded if you wish to continue using OpenStreetMap data for Enhanced Speed Control and road name display.\n\n%1":
    "OpenStreetMap 資料庫已過期。若需繼續使用開放街圖資料進行增強速度控制和道路名稱顯示，必須下載新地圖。\n\n%1",
  "Poor visibility detected for driver monitoring. Ensure the device has a clear view of the driver. This can be checked in the device settings. Extreme lighting conditions and/or unconventional mounting positions may also trigger this alert.":
    "駕駛員監控能見度不佳。請確保設備能清楚看到駕駛員。可在設備設定中檢查。極端光照和/或非傳統安裝位置也可能觸發此警報。",
  "Excessive %1 actuation detected on your last drive. Please contact support at https://comma.ai/support and share your device's Dongle ID for troubleshooting.":
    "偵測到上次駕駛中 %1 過度操控。請聯絡 https://comma.ai/support 支援並提供設備 Dongle ID 以進行故障排除。",
  "<b>Unsupported branch detected</b> - The current version of <b><u>%1</u></b> branch is no longer supported on the comma three. Please go to <b>[Device > Software]</b> and install a supported branch with <b><u>-tici</u></b> in the branch name for the comma three.":
    "<b>偵測到不受支援的分支</b> - 當前 <b><u>%1</u></b> 分支版本已不再支援 comma three。請前往 <b>[設備 > 軟體]</b> 安裝分支名稱包含 <b><u>-tici</u></b> 的受支援分支。",
})


def apply_translations(po_path: Path, mapping: dict[str, str]) -> int:
  text = po_path.read_text(encoding="utf-8")
  updated = 0
  for msgid, msgstr in mapping.items():
    escaped_id = msgid.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    escaped_str = msgstr.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    # multiline msgid/msgstr blocks
    if "\n" in msgid:
      id_block = 'msgid ""\n' + "".join(f'"{line}\\n"\n' for line in msgid.split("\n"))
      str_block = 'msgstr ""\n' + "".join(f'"{line}\\n"\n' for line in msgstr.split("\n"))
      pattern = re.compile(re.escape(id_block.rstrip("\n")) + r"\nmsgstr \"\"\n", re.MULTILINE)
      if pattern.search(text):
        text = pattern.sub(id_block + str_block, text, count=1)
        updated += 1
        continue
    pattern = f'msgid "{escaped_id}"\nmsgstr ""'
    replacement = f'msgid "{escaped_id}"\nmsgstr "{escaped_str}"'
    if pattern in text:
      text = text.replace(pattern, replacement, 1)
      updated += 1
    elif f'msgid "{escaped_id}"\nmsgstr "{escaped_id}"' in text or True:
      # update existing wrong translation
      pat2 = re.compile(rf'msgid "{re.escape(escaped_id)}"\nmsgstr ".*?"', re.DOTALL)
      m = pat2.search(text)
      if m and msgid in text:
        old = m.group(0)
        new = f'msgid "{escaped_id}"\nmsgstr "{escaped_str}"'
        if old != new:
          text = text.replace(old, new, 1)
          updated += 1
  po_path.write_text(text, encoding="utf-8")
  return updated


def main():
  n1 = apply_translations(TRANSLATIONS / "app_zh-CHS.po", ZH_CHS)
  n2 = apply_translations(TRANSLATIONS / "app_zh-CHT.po", ZH_CHT)
  print(f"Updated zh-CHS: {n1}, zh-CHT: {n2}")


if __name__ == "__main__":
  main()
