# SCPI 与官方资料

2026-10-28 核对官方入口：https://www.rigolna.com/support/downloads/

- [MSO2000A/DS2000A Programming Guide](https://beyondmeasure.rigoltech.com/acton/attachment/1579/f-0508/1/-/-/-/-/MSO2000A%26DS2000A_ProgrammingGuide.pdf)：2019-05，PGA18106-1110，文档对应软件 00.03.04.SP2。
- [MSO2000A/DS2000A User Guide](https://beyondmeasure.rigoltech.com/acton/attachment/1579/f-0509/1/-/-/-/-/MSO2000A%26DS2000A_UserGuide.pdf)：接线、探头、远程接口章节。
- [PyVISA 二进制读取](https://pyvisa.readthedocs.io/en/1.15.0/introduction/rvalues.html)。脚本用 INSTR 消息边界 `read_raw` 读取，再严格解析 IEEE definite-length block；不以换行切割二进制。

本机查阅缓存（不属于 skill 的可移植依赖）：`~/.cache/rigol-ds2000a/{programming,user}.{pdf,txt}`。缓存不存在时从官方链接重新下载，检查确为 PDF，再用 `pdftotext -layout` 按命令检索。不把整本手册加入技能上下文。

## 已核对的命令与差异

| 用途 | 命令/规则 |
| --- | --- |
| 身份、状态 | `*IDN?`、`:TRIG:STAT?`、`:ACQ:SRAT?`、`:ACQ:MDEP?` |
| 选件报告 | `:SYST:OPT:VAL? TRIG`，另有 DEC、CAN、MEMD；手册 2-268，查询不写激活信息 |
| 通道配置读回 | `:CHAN1:DISP?`、`:CHAN1:PROB?`、`:CHAN1:SCAL?`、`:CHAN1:OFFS?`、`:CHAN1:COUP?`、`:CHAN1:UNITs?` |
| 测量 | `:MEAS:FREQ? CHAN1`、`:MEAS:VPP? CHAN1`、`:MEAS:VRMS? CHAN1`；不要照抄 DS1000Z 的 `:MEAS:ITEM?` |
| 截图 | `:DISP:DATA?`，返回长度头加 BMP；不加其他系列的 PNG 参数 |
| 波形 | `:WAV:SOUR CHAN1`、`:WAV:MODE NORM/RAW`、`:WAV:FORM BYTE`、`:WAV:PRE?`、`:WAV:DATA?` |
| 错误队列 | `:SYST:ERR?` 会取出并删除一条错误，仅在诊断需要时使用并保存结果 |

脚本将 `*IDN?` 作为连接后的首条指令，识别家族后才查询其余命令。测量查询会启用测量项目，不能仅因带问号就认为无副作用。未确认的选件、数字通道、AWG 命令查手册后再用。

实测固件 00.03.05.SP4 的截图：IEEE 块内 1152054 字节完整，但 BMP 的 bfSize 字段为 1152000（仅像素区）。脚本同时核对 800×480、24 位未压缩、54 字节头及精确像素长度，接受该已确认差异，保留原始字节；不泛化为忽略长度错误。

## 波形读取（手册 2-361 至 2-375）

NORM 是屏幕数据，RAW 是停止采集后的内存数据。BYTE 每次最多 250000 点，WORD 125000，ASCII 15625；不要套用 DS1000Z 的块长。RAW 支持逐块设 STAR/STOP 后 DATA?，无需混入连续读取模式的 BEG/END/RES。文档 STAR 范围表的 RAW 起点印为 11，但同章块读取示例明确从 1 开始；脚本按示例从 1 开始并回读验证，固件拒绝时停止，不悄悄丢前 10 点。

PREamble 含格式、模式、点数、平均次数及 X/Y 增量、原点、参考值共十项。BYTE 波形使用：

```text
t[i] = (i - xreference) * xincrement + xorigin
y[i] = (byte[i] - yreference - yorigin) * yincrement
```

i 为从 0 开始的全记录索引，分块时不能每块重新从 0 计时。Y 单位取通道 UNITs，不能一律写 V。探头倍率已反映在仪器缩放中，不重复乘倍率。保留 preamble、BYTE 原文件、通道配置和采集状态。短块、长度不符、量程变化或状态变化时停止并把已有文件视为未完成。

## 按需配置

用户要求调整时基/触发/停止采集即授权相应操作，不需要重复确认。先读取旧值，再按手册写最小改动并回读，例如 `:TIM:SCAL?` / `:TIM:SCAL 数值`、`:CHAN1:SCAL?` / `:CHAN1:SCAL 数值`。探头倍率须匹配物理开关。`:STOP` 会改变采集；`:RUN` 会继续采集；`:SING` 会重新布防；`:AUT` 会改变多项设置，都不能作为连通性测试。脚本不自动执行这些命令。
