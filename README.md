# video-uploader

YouTube视频字幕处理与上传工具

## 功能

- 📥 YouTube视频下载
- 📝 字幕获取（YouTube字幕 / Whisper语音识别）
- ✨ LLM字幕矫正（支持 OpenAI 和 MiniMax）
- 🔥 字幕烧录（支持中英双语）
- 📤 B站扫码上传
- 📱 抖音手动上传引导

## 安装

```bash
# 1. 克隆项目
git clone https://github.com/ZZZZihan/video-uploader.git
cd video-uploader

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装系统依赖
# macOS - 需要ffmpeg-full才支持字幕烧录
brew install ffmpeg
# 如果需要字幕烧录，安装完整版
# brew install ffmpeg-full

# Ubuntu
sudo apt install ffmpeg

# Windows
# 下载 https://ffmpeg.org/download.html

# 5. 安装yt-dlp浏览器支持（用于下载受保护的视频）
# 需要先在Chrome/Safari登录YouTube
pip install curl_cffi
```

## 配置

```bash
# 复制配置示例
cp config/settings.yaml.example config/settings.yaml

# 编辑配置，填入你的 API Key
# - OPENAI_API_KEY: OpenAI API 密钥
# - MINIMAX_API_KEY: MiniMax API 密钥
```

支持环境变量配置：
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`

### 刷新YouTube Cookie（重要！）

YouTube Cookie会过期，需要定期刷新：

```bash
# 在Chrome登录YouTube后执行
mkdir -p cookies
yt-dlp --cookies-from-browser chrome --cookies cookies/youtube.txt "https://www.youtube.com/watch?v=xxx" --skip-download
```

## 使用

### 注意事项

⚠️ **YouTube视频下载**：部分视频有SABR保护，可能导致下载失败或画质受限。解决方案：
1. 使用代理/VPN
2. 刷新Cookie后重试
3. 视频有保护时默认回退到360p

### 下载视频

```bash
# 默认下载1080p（受保护视频会回退到360p）
python cli.py download --url "https://www.youtube.com/watch?v=xxx"

# 指定更高画质（需要代理或Cookie有效）
python cli.py download --url "https://www.youtube.com/watch?v=xxx" --format "bestvideo[height<=2160]+bestaudio/best"

# 指定360p（最快，最稳定）
python cli.py download --url "https://www.youtube.com/watch?v=xxx" --format "18"

# 使用代理
python cli.py download --url "URL" --proxy "http://127.0.0.1:7890"
```

### 获取字幕

```bash
# 自动选择字幕来源（优先YouTube，无则Whisper）
python cli.py subtitle --url "https://www.youtube.com/watch?v=xxx"

# 指定使用Whisper识别
python cli.py subtitle --url "https://www.youtube.com/watch?v=xxx" --source whisper

# 使用LLM矫正字幕
python cli.py subtitle --url "https://www.youtube.com/watch?v=xxx" --correct-with openai
python cli.py subtitle --url "https://www.youtube.com/watch?v=xxx" --correct-with minimax
```

### 烧录字幕

```bash
# 单字幕
python cli.py burn --video input.mp4 --subtitle subtitle.srt --output output.mp4

# 双语字幕（中英）
python cli.py burn --video input.mp4 --subtitle chinese.srt --secondary-subtitle english.srt --output output.mp4
```

### 上传B站

```bash
# 扫码登录（首次）
python cli.py upload-bilibili --video output.mp4 --title "视频标题" --tags "标签1,标签2" --scan-login

# 已有Cookie（直接上传）
python cli.py upload-bilibili --video output.mp4 --title "视频标题" --no-scan-login
```

### 抖音引导

```bash
python cli.py upload-douyin --video output.mp4 --caption "抖音文案"
```

## 命令行选项

### 全局选项

- `--config-file`: 配置文件路径（默认 config/settings.yaml）
- `--output`: 默认输出目录
- `--proxy`: 代理地址

### download

- `--url`: YouTube视频URL（必需）
- `--format`: 格式选择器（默认 bestvideo+bestaudio/best）
- `--cookies`: YouTube Cookie文件

### subtitle

- `--url`: YouTube视频URL
- `--video`: 本地视频文件（Whisper用）
- `--language`: 字幕语言代码（默认 zh）
- `--source`: 来源选择（auto/youtube/whisper）
- `--model-size`: Whisper模型大小（tiny/base/small/medium/large）
- `--correct-with`: LLM矫正（none/openai/minimax）

### burn

- `--video`: 输入视频（必需）
- `--subtitle`: 主字幕文件（必需）
- `--secondary-subtitle`: 第二字幕（双语）
- `--style`: ASS样式覆盖

## 项目结构

```
video-uploader/
├── cli.py                    # CLI入口
├── config/
│   ├── config.py            # 配置管理
│   └── settings.yaml.example # 配置示例
├── downloader/
│   └── youtube.py           # YouTube下载
├── subtitle/
│   ├── handler.py           # 字幕主逻辑
│   ├── downloader.py       # YouTube字幕
│   ├── whisper.py          # Whisper识别
│   └── llm_correction.py   # LLM矫正
├── burner/
│   └── ffmpeg.py           # 字幕烧录
├── uploader/
│   ├── bilibili.py         # B站上传
│   └── douyin.py           # 抖音引导
└── utils/
    └── cookie.py           # Cookie管理
```

## 许可证

MIT
