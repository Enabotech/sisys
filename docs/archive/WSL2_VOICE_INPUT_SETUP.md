# WSL2 语音输入工作流配置指南

## 概述

本文档描述如何在 WSL2 Ubuntu 22.04 环境下搭建"语音 → 文字直接输入 Claude Code 终端"的高效工作流。

**目标**：通过语音输入，文字直接注入到终端，彻底摆脱键盘打字。

---

## 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 11 + WSLg |
| 发行版 | Ubuntu 22.04 (WSL2) |
| 麦克风 | 任意可用麦克风/耳机（需在 Windows 中授权） |
| 网络 | 可选（用于安装依赖） |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│  Windows 11 + WSLg                                          │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐                       │
│  │ 麦克风/耳机   │───▶│  WSLg        │───▶ PulseAudio     │
│  └─────────────┘    │  RDPSource   │   (unix socket)       │
│                     └──────────────┘                       │
│                              │                              │
│               /mnt/wslg/runtime-dir/pulse/native           │
│                              │                              │
│                    ┌─────────▼──────────────────────────┐  │
│                    │  WSL2 Ubuntu                        │  │
│                    │                                     │  │
│                    │  parec ──▶ ffmpeg ──▶ Whisper     │  │
│                    │  录音      转换      识别           │  │
│                    │                                     │  │
│                    │  PowerShell SendKeys ──▶ 终端输入   │  │
│                    └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ 当前状态

**WSLg 音频不稳定**，麦克风功能需要每次重启 WSL 后验证。

如果主要使用语音输入，建议考虑：
- Mac 作为开发机（原生支持，稳定）
- 手机作为麦克风（绕过 WSLg 问题）

---

## ⚠️ 重要经验总结

### 实际验证结论

| 组件 | 状态 | 说明 |
|------|------|------|
| WSLg PulseAudio | ⚠️ 不稳定 | 连接容易断开，需重启 WSL |
| parec 录音 | ✅ 正常 | WSLg 音频正常时工作 |
| ffmpeg 转换 | ✅ 正常 | 将 raw 音频转为标准 WAV |
| Whisper 识别 | ✅ 正常 | 中文识别效果良好 |
| xdotool | ❌ 不工作 | WSLg Wayland 不支持 uinput |
| PowerShell SendKeys | ✅ 正常 | 可行但需要窗口焦点 |
| xbindkeys | ✅ 正常 | 快捷键绑定工作正常 |

### 关键教训

1. **WSLg 音频连接不稳定**：`/mnt/wslg/runtime-dir/pulse/native` socket 容易失效
2. **xdotool 在 Wayland 下不工作**：需要用 PowerShell 模拟键盘
3. **Whisper 命令行输出被抑制**：需要重定向到文件或用 Python API
4. **窗口焦点问题**：PowerShell SendKeys 需要目标窗口有焦点

---

## 实施步骤

### Phase 1：安装依赖

```bash
# 系统依赖
sudo apt update
sudo apt install -y ffmpeg pulseaudio-utils

# Python 依赖（使用清华源加速）
pip3 install openai-whisper -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **注意**：xbindkeys 已安装但非必需，如不使用快捷键可忽略

### Phase 2：创建语音输入脚本

创建 `~/bin/voicein`：

```bash
#!/bin/bash
# voicein - 语音输入脚本

set -e

DURATION=${1:-15}
export PULSE_SERVER="unix:/mnt/wslg/runtime-dir/pulse/native"

TMP_DIR="/tmp/voicein_$$"
mkdir -p "$TMP_DIR"
REC_FILE="$TMP_DIR/rec.wav"
CONV_FILE="$TMP_DIR/conv.wav"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

echo "🎤 开始录音（${DURATION}秒）..."

# 录音（使用 PulseAudio 的 parec）
parec -d RDPSource --rate=16000 --format=s16le -r "$REC_FILE" &
PID=$!
sleep "$DURATION"
kill $PID 2>/dev/null; wait $PID 2>/dev/null || true

# 转换音频格式（parec 输出需要转换）
ffmpeg -f s16le -ar 16000 -ac 1 -i "$REC_FILE" -acodec pcm_s16le "$CONV_FILE" -y 2>/dev/null

echo "🔄 识别中..."

# 用 Python 调用 Whisper
TEXT=$(python3 - "$CONV_FILE" << 'PYEOF'
import whisper
import sys
model = whisper.load_model("tiny")
result = model.transcribe(sys.argv[1], language="zh", fp16=False, verbose=False)
print(result["text"])
PYEOF
)

if [ -z "$TEXT" ]; then
    echo "⚠️  未识别到文字"
    exit 1
fi

echo "✅ 识别结果: $TEXT"
echo ""
echo "⚠️  请在 2 秒内点击目标窗口..."
sleep 2

# 使用 PowerShell 发送文字到焦点窗口
powershell.exe -c "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('$TEXT')" 2>/dev/null

echo "✓ 完成"
```

赋予执行权限：

```bash
chmod +x ~/bin/voicein
```

### Phase 3：配置别名（推荐）

不需要快捷键，直接用命令。在 `~/.bashrc` 添加：

```bash
# 语音输入别名
alias v='~/bin/voicein'
alias vp='~/bin/voicein 5'   # 快速5秒
```

使配置生效：

```bash
source ~/.bashrc
```

---

## 使用方法

在终端直接输入：

```bash
v          # 默认录音15秒
vp         # 快速录音5秒
v 30       # 录音30秒
```

工作流程：
1. 输入 `v` 回车
2. 对着麦克风说话
3. 等待识别完成
4. 提示"请在 2 秒内点击目标窗口"后点击目标窗口
5. 文字自动输入

---

## WSLg 音频问题排查

### 检查 PulseAudio 连接

```bash
# 检查 socket 是否存在
ls -la /mnt/wslg/runtime-dir/pulse/

# 检查连接状态
export PULSE_SERVER="unix:/mnt/wslg/runtime-dir/pulse/native"
pactl info
```

### 重启 WSLg 音频

如果麦克风无法录音，需要重启 WSLg：

```powershell
# 在 Windows PowerShell 中运行
wsl --shutdown
# 然后重新打开 Ubuntu 终端
```

### 验证麦克风

```bash
export PULSE_SERVER="unix:/mnt/wslg/runtime-dir/pulse/native"

# 录音测试
parec -d RDPSource --rate=16000 --format=s16le -r /tmp/test.wav &
sleep 3
kill %1 2>/dev/null

# 检查音量
ffmpeg -i /tmp/test.wav -af "volumedetect" -f null /dev/null 2>&1 | grep max_volume
```

---

## 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| parec 录音文件为空 | PulseAudio 未连接 | 重启 WSLg 或检查 `PULSE_SERVER` |
| 麦克风无声音 | Windows 权限 | 在 Windows 音频设置中允许麦克风访问 |
| Whisper 无输出 | 命令行输出被抑制 | 使用 Python API 或 `--verbose True` |
| PowerShell 不输入 | 窗口无焦点 | 识别后点击目标窗口 |
| xbindkeys 不响应 | 配置路径问题 | 使用绝对路径 `/home/agimtech/bin/voicein` |

---

## 替代方案

### 方案 1：手机作为麦克风（更稳定）

```
手机录音 → 通过 SSH 传输 → WSL2 Whisper 识别 → PowerShell 输入
```

### 方案 2：Windows 原生语音输入

```bash
# 使用 Windows 语音识别，结果通过管道传入
powershell.exe -c "Add-Type -AssemblyName System.Speech; ..."
```

### 方案 3：使用已配置好的商业方案

- **Talon Voice**：专为编程设计，但付费
- **Dragon Professional**：精度最高，昂贵
- **Mac + Siri**：原生支持，体验最佳

---

## 文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| 语音输入脚本 | `~/bin/voicein` | 录音+识别+注入 |
| 快捷键配置 | `~/.xbindkeysrc` | Ctrl+Alt+v 绑定 |

---

## 参考资源

- [OpenAI Whisper](https://github.com/openai/whisper)
- [WSLg 官方文档](https://docs.microsoft.com/en-us/windows/wsl/tutorials/gui-packages)
- [PowerShell SendKeys](https://docs.microsoft.com/en-us/dotnet/api/system.windows.forms.sendkeys)

---

## 已安装内容清单

### 系统包（apt）

| 包名 | 版本 | 路径 | 用途 |
|------|------|------|------|
| ffmpeg | 7:4.4.2 | `/usr/bin/ffmpeg` | 音频格式转换 |
| xbindkeys | 1.8.7 | `/usr/bin/xbindkeys` | 快捷键绑定 |
| pulseaudio-utils | 1:15.99.1 | `/usr/bin/parec` (→pacat) | PulseAudio 客户端 |

### Python 包（pip）

| 包名 | 版本 | 路径 | 用途 |
|------|------|------|------|
| openai-whisper | 20240930 | `~/.local/lib/python3.10/site-packages/` | 语音识别引擎 |

### Whisper 模型

| 模型 | 大小 | 路径 |
|------|------|------|
| tiny | ~75MB | `~/.cache/whisper/tiny.pt` |
| small | ~255MB | `~/.cache/whisper/small.pt` |

模型首次使用时自动下载，之后无需网络。

### 创建的文件

| 文件 | 路径 | 用途 |
|------|------|------|
| 语音输入脚本 | `~/bin/voicein` | 录音+识别+输入 |
| 快捷键配置 | `~/.xbindkeysrc` | xbindkeys 配置（可忽略） |

### ~/.bashrc 添加的内容

```bash
# 第132行：PulseAudio 配置
export PULSE_SERVER="unix:/mnt/wslg/runtime-dir/pulse/native"

# 第135-139行：xbindkeys 自启动
if ! pgrep -x xbindkeys > /dev/null 2>&1; then
    sleep 1
    xbindkeys 2>/dev/null || true
fi

# 第142-143行：语音输入别名
alias v='~/bin/voicein'
alias vp='~/bin/voicein 5'
```

---

## 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-19 | 1.0 | 初始版本 |
| 2026-04-19 | 1.1 | 更新实际验证结论，添加 WSLg 音频问题说明 |
| 2026-04-19 | 1.2 | 添加已安装内容清单，使用别名替代快捷键 |
