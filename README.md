# RIGOL DS2072A Codex Skill

通过 USBTMC 或 LAN/VXI-11 连接 RIGOL DS2072A / DS2000A 的 Codex 技能及 Python CLI。支持身份与选件查询、测量、BMP 截图、屏幕和深存储波形导出。

A Codex skill and Python CLI for RIGOL DS2000A oscilloscopes over USBTMC or VXI-11. Capture screenshots and waveforms without automatically stopping or restarting acquisition. Firmware-reported model/option status is kept separate from verified hardware capability.

## 安装

需要 Python 3.7+（建议使用仍受维护的 Python 版本）、Git；USB 通信还需要系统 libusb。以下安装到默认 Codex skills 目录，若目标目录已有内容，请先检查，不覆盖现有安装。

```bash
git clone https://github.com/waxer-501/rigol-ds2072a.git "$HOME/.codex/skills/rigol-ds2072a"
python3 -m venv "$HOME/.local/share/rigol-ds2072a/venv"
"$HOME/.local/share/rigol-ds2072a/venv/bin/pip" install -r "$HOME/.codex/skills/rigol-ds2072a/requirements.txt"
```

在能够发现该 skill 的 Codex 会话中说：

> 用 $rigol-ds2072a 连接示波器，查询状态并保存当前屏幕。

入口为 [SKILL.md](SKILL.md)，连接排障见 [connection.md](references/connection.md)，命令依据见 [scpi.md](references/scpi.md)。

## 接线与快速使用

- USB：电脑 → 示波器后面 **USB DEVICE Type-B 方口**；前面 USB HOST 长方形口不用于电脑控制。
- LAN：使用示波器面板的 IP/VISA 地址，资源示例 `TCPIP0::192.0.2.10::inst0::INSTR`，须替换为实际地址。
- 探头接内置补偿方波时，核对物理探头倍率和通道倍率。普通探头地夹连接保护地。

```bash
PY="$HOME/.local/share/rigol-ds2072a/venv/bin/python"
SCOPE="$HOME/.codex/skills/rigol-ds2072a/scripts/scope.py"
"$PY" "$SCOPE" discover
# 从实际发现结果复制完整 USB 资源；不要使用示例序列号。
RESOURCE='替换成实际 VISA 资源'
"$PY" "$SCOPE" --resource "$RESOURCE" info
"$PY" "$SCOPE" --resource "$RESOURCE" options
"$PY" "$SCOPE" --resource "$RESOURCE" screenshot --output /tmp/scope.bmp
"$PY" "$SCOPE" --resource "$RESOURCE" measure --channel 1
"$PY" "$SCOPE" --resource "$RESOURCE" waveform --channel 1 --output /tmp/ch1.csv
```

`measure` 会启用对应测量项目。NORM 导出会暂时改变并恢复波形传输设置，最多 1400 点；运行中的读取不是冻结快照。输出包括 CSV、原始 BYTE 和 JSON 元数据。

完整内存读取使用 `waveform --mode RAW --points N`，必须已经停止采集，N 要依据当前配置选择。脚本不会自动发送 STOP/RUN、AUTO、复位、校准或固件/选件写入。发生通信异常后关闭连接，不自动重试或恢复；终端会给出修改前的传输参数。

## 测试与验证范围

```bash
python3 scripts/test_scope.py
```

离线测试覆盖二进制长度头、内嵌换行、缩放、分块导出、状态恢复、短包失败及运行中 RAW 拒绝。离线测试不代表实机通过；LAN、深存储及各固件版本均需单独验证。实机验证进展记录在本节，不发布个人设备序列号、捕获数据或本地凭据。

## 来源与许可

[官方手册及命令出处](references/scpi.md)。RIGOL 手册仅链接，不随仓库分发；RIGOL 商标属于其权利人。本项目为独立社区工具，代码及原创说明采用 [MIT License](LICENSE)。不提供破解、密钥生成或固件改写功能；已解锁设备也只使用文档化接口。
