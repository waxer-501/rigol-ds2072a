# 连接与差异

## USB

电脑接示波器后面 **USB DEVICE（方形 Type-B）**。前面 USB HOST（Type-A）不是电脑控制接口。电脑端可为 Type-C，但必须是支持数据的线。示波器开机后检查：

```bash
lsusb
ls -l /dev/usbtmc* 2>/dev/null
```

厂商 ID 通常为 `1ab1`；PID/序列号以当前枚举为准。改型号设备不能硬编码 PID。没有出现在 `lsusb` 时先检查供电、接口和数据线，安装 Python 驱动不能解决 USB 未枚举。

## Python 环境

```bash
python3 -m venv "$HOME/.local/share/rigol-ds2072a/venv"
"$HOME/.local/share/rigol-ds2072a/venv/bin/pip" install pyvisa pyvisa-py pyusb
```

使用 `pyvisa.ResourceManager('@py')`，USB 依赖 PyUSB 和系统 libusb；LAN/VXI-11 不需要厂商 Windows 软件。不要默认安装 NI-VISA 或替换系统 Python。官方依赖说明：https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/installation.html

USB 权限不足时先检查具体 `/dev/bus/usb/BBB/DDD` 的 ACL 与占用者。仅对当前仪器 VID/PID/序列号配置精确 udev 权限（本地桌面可用 `TAG+="uaccess"`）；不要全局放开 USB 权限，不使用 `chmod 666 /dev/bus/usb/*/*`。kernel usbtmc 与 libusb 冲突时先确认没有其他程序使用仪器，不全局卸载驱动。网络可用时也可选择 LAN。

## LAN

从 Utility → IO Setting → LAN Set 获取 IP 和 VISA 地址。同一网络中显式使用 `TCPIP0::实际IP::inst0::INSTR`。优先 VXI-11；不要假定 DS2000A 支持其他系列常见的 5555/5025 原始套接字端口。脚本只支持 USB INSTR 和 TCPIP INSTR，依赖消息边界读取二进制。

## 已破解设备

先保存 `*IDN?` 原始值；需要核对选件时使用脚本 `options`，发送手册定义的 `:SYST:OPT:VAL? TRIG/DEC/CAN/MEMD` 四种查询（每次一个参数），而非未经该手册确认的通用 `*OPT?`。0/1/2/3 分别表示未安装/试用过期/已安装/有效试用，这仅是固件报告状态。型号变化不自动视为连接错误，仍检查 RIGOL DS/MSO 2000A 家族。不要以“解决兼容问题”为由升级、降级、恢复出厂或改写激活信息。较老固件不支持某命令时记录命令与错误，并查对应历史手册。
