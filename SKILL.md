---
name: rigol-ds2072a
description: 通过 USBTMC 或 LAN/VXI-11 连接 RIGOL DS2072A / DS2000A 示波器，查询状态和测量值、截图、导出波形并按需设置采集与触发；支持已改型号或解锁选件设备的差异核对，保留现有固件和授权状态。
---

# DS2072A 接入

先读 [连接与设备差异](references/connection.md)。命令依据、波形换算和高级设置见 [SCPI 与资料](references/scpi.md)。配套脚本是实际通信工具，不需要额外 MCP 服务。

## 工作边界

- 对于机身为 DS2072A、已改型号或解锁选件的设备，把机身型号、`*IDN?` 返回值、固件和实测能力分别记录。不要由 DS2302A 等返回值推断真实模拟带宽、校准精度、存储深度或已具备 -S 信号源/数字通道硬件。
- 接入先枚举，再对用户指定的单台设备查询身份、采集状态。默认不发送 STOP/RUN/SINGLE/AUTO、复位、自校准、固件更新、选件写入、工厂/破解指令，也不主动启用信号输出。
- 用户已要求的截图、波形导出、参数调整可直接在其授权范围内完成，不逐条重复确认。导出会改动波形传输参数，应如实说明。若要停止当前采集而任务未授权，先取得许可；用户手动 STOP 也可。
- 超时或二进制包异常即停止该次事务并关闭连接，不盲目重试或继续往未同步的会话发命令。报告哪些设置可能已改变。查询错误队列会消费错误消息，不作为无副作用的常规查询。
- 接探头时确认探头倍率、通道倍率及接地点；普通探头地夹与保护地相连，不能夹到带电高侧。自带探头补偿方波和 -S 机型信号源是不同功能。

## 工具使用

本机解释器：`~/.local/share/rigol-ds2072a/venv/bin/python`。若不存在，按连接文档创建独立环境。脚本路径相对本技能目录：`scripts/scope.py`。

```bash
PY="$HOME/.local/share/rigol-ds2072a/venv/bin/python"
SCOPE="$HOME/.codex/skills/rigol-ds2072a/scripts/scope.py"
"$PY" "$SCOPE" discover
# RESOURCE 替换成实际 USB VISA 资源或 TCPIP0::实际IP::inst0::INSTR
"$PY" "$SCOPE" --resource "$RESOURCE" info
"$PY" "$SCOPE" --resource "$RESOURCE" options
"$PY" "$SCOPE" --resource "$RESOURCE" measure --channel 1
"$PY" "$SCOPE" --resource "$RESOURCE" screenshot --output /tmp/scope-screen.bmp
"$PY" "$SCOPE" --resource "$RESOURCE" waveform --channel 1 --output /tmp/scope-ch1.csv
```

- `discover` 只枚举 USB，不扫描局域网、不自动选第一台。LAN 使用示波器面板显示的 IP/VISA 地址。
- `info`、`screenshot` 不改变采集配置。`measure` 的查询按手册会启用对应测量项目，可能改变屏幕测量显示；用户要求测量时可执行，纯身份检查不用它。不能把 USB 枚举成功当作 SCPI 已通。
- `waveform` 默认 NORM，最多 1400 个屏幕点，保存 CSV、原始 BYTE 和 JSON 元数据；这不是完整采样内存。运行中读取标注为非冻结快照，不保证同一帧。
- `waveform --mode RAW --points N` 只在已 STOP 时工作，每块不超过 250000 点；脚本从不自行 STOP/RUN。N 应基于当前配置/返回值，不根据破解宣传推断。通道必须已打开。
- 正常导出会恢复传输设置并回读；通信失败不尝试自动恢复。脚本不修改时基、量程、触发、探头倍率或通道开关。
- 修改采集/触发参数时，按 SCPI 文档使用小范围 PyVISA 操作，记录修改前后值并回读；脚本不提供任意命令批量写入入口。

## 验证与交付

先身份查询，再屏幕/测量，最后按用户任务需要导出波形。接自带方波时核对屏幕频率、Vpp、探头倍率和 CSV 的周期/幅值；以屏幕和实际查询为准。无效测量值 `9.9e37` 不当成真实信号。

报告资源、设备返回的型号/固件、初末采集状态、文件路径和证据等级。离线测试通过不代表硬件验证通过；截图成功也不代表深存储读取或破解后带宽已验证。
