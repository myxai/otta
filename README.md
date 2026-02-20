# nanobot Desktop

A Windows desktop GUI client for [nanobot](https://github.com/HKUDS/nanobot) — the ultra-lightweight personal AI assistant.

[中文说明](README_CN.md)

## Features

- **Chat** — Real-time conversation with the nanobot AI agent, with Markdown rendering and code highlighting
- **Settings** — Visual configuration for API keys, model parameters, MCP tool servers, channel toggles, and more
- **Status** — Overview of system status: providers, channels, model config, MCP tools, and feedback cases
- **Gateway** — Start / stop the nanobot gateway with one click to connect Telegram, Discord, Feishu, etc.
- **MCP Integration** — Connect external tool servers (e.g. Playwright for browser automation) via MCP protocol
- **i18n** — Bilingual UI (Chinese / English), defaults to system language

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.10+ | Required |
| **Edge WebView2 Runtime** | — | Pre-installed on Windows 10 (2004+) / 11. [Download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) if missing |
| **Node.js** (optional) | 18+ | Only needed for MCP tool servers (e.g. Playwright browser automation). [Download](https://nodejs.org/) |
| **LLM API Key** | — | At least one provider key (e.g. DashScope, OpenAI, DeepSeek, Anthropic). Configure in the Settings page after launch |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. First-time setup

If nanobot has not been initialized, the app will guide you through the process. You can also run manually:

```bash
nanobot onboard
```

### 3. Launch the desktop app

```bash
python app.py
```

A native Windows window will open. If `pywebview` is not installed, it will fall back to browser mode.

## Tech Stack

| Layer | Technology |
|---|---|
| Native window | pywebview (Edge WebView2) |
| Backend API | Flask |
| Frontend | Vanilla HTML / CSS / JS |
| Markdown rendering | marked.js |
| Code highlighting | highlight.js |
| AI engine | nanobot-ai |

## Project Structure

```
myai/
├── app.py              # Main app: Flask backend + pywebview window
├── requirements.txt    # Python dependencies
├── README.md           # English documentation
├── README_CN.md        # Chinese documentation
└── frontend/
    ├── index.html      # Frontend page
    ├── style.css       # Styles (Catppuccin Mocha dark theme)
    └── app.js          # Frontend logic (with i18n)
```

## Configuration

All settings are stored in `~/.nanobot/config.json` and can be edited visually through the Settings page in the app.

### Key settings

- **Model** — Enter the model name in Settings (e.g. `qwen-plus`, `deepseek-chat`, `claude-opus-4-5`)
- **API Key** — Fill in provider keys under the "API Keys" section
- **MCP Servers** — Add tool servers (like Playwright) under "MCP Tool Services"
- **Channels** — Toggle channel switches; use the Advanced JSON Editor for detailed channel config
- **Language** — Switch between Chinese and English in the sidebar or Settings page

### Model provider recommendation

Most LLM providers (DashScope / DeepSeek / Moonshot / SiliconFlow / Groq, etc.) offer an **OpenAI-compatible** API endpoint. It is recommended to configure them under the **OpenAI** provider:

1. Go to **Settings → API Keys → openai**
2. Set **API Key** to the key from your provider
3. Set **API Base** to the provider's OpenAI-compatible endpoint, for example:

| Provider | API Base |
|---|---|
| DashScope (Qwen) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot (Kimi) | `https://api.moonshot.cn/v1` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

4. Set the **Model** name to the model you want to use (e.g. `qwen-plus`, `deepseek-chat`)

This approach provides the best compatibility and avoids per-provider SDK issues.
