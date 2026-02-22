# MyxAI Desk

A desktop GUI client for [nanobot](https://github.com/HKUDS/nanobot) — the ultra-lightweight personal AI assistant.

[中文说明](README_CN.md)

## Features

- **Chat** — Real-time conversation with the nanobot AI agent, with Markdown rendering and code highlighting
- **Apps** — Extensible app center; install, configure, and manage automated tasks
  - **Today's Reading** — AI-powered personal interest recommendation engine based on browser history and chat conversations
  - **Web Monitor** — Track changes on web pages with hash comparison or LLM-powered smart summaries
  - **Email Summary** — Connect via IMAP, read recent emails, and generate daily AI-powered summaries
  - **Focus Timer** — Full Pomodoro timer with custom durations, task tags, and statistical charts
  - **Custom Apps** — Turn any nanobot conversation into a reusable, scheduled application
- **Settings** — Visual configuration for API keys, model parameters, MCP tool servers, channel toggles, and more
- **Status** — Overview of system status: providers, channels, model config, MCP tools, and feedback cases
- **Gateway** — Start / stop the nanobot gateway with one click to connect Telegram, Discord, Feishu, etc.
- **MCP Integration** — Connect external tool servers (e.g. Playwright for browser automation) via MCP protocol
- **i18n** — Bilingual UI (Chinese / English), defaults to system language

## Today's Reading App

An automated daily recommendation engine that analyzes your browser history **and nanobot conversation history**, then searches the web for high-quality content tailored to your interests.

**How it works:**

1. **Collect** — Reads Chrome / Edge browsing history (titles & URLs only) **plus recent nanobot chat conversations** (topics discussed with the AI)
2. **Analyse** — LLM identifies your real interests from both sources and classifies them (work / study / life)
3. **Search** — Generates semantic search queries and searches the web (Brave → Bing → DuckDuckGo auto-fallback)
4. **Curate** — LLM selects the best content from search results, generates an HTML report with real links

**Key design:**

- No browser plugins required; works with local history database
- Analyses both browsing behaviour and AI conversation topics for deeper interest understanding
- AI-powered interest extraction (falls back to rule-based when LLM unavailable)
- Multi-engine web search with automatic failover
- Structured HTML report with card layout
- Scheduled auto-generation or manual trigger
- Interest preview for quick analysis without full report

## Web Monitor App

Monitor any web page for changes and get notified automatically.

- **Hash mode** — Fast SHA-256 comparison of extracted page text, no LLM cost
- **LLM mode** — Uses AI to summarise exactly what changed between page versions
- Configurable check interval (default 30 minutes)
- Change history with timestamped summaries
- Manual or scheduled automatic checks

## Email Summary App

Connect your email via IMAP and get a concise daily summary.

- **Built-in IMAP** — Uses Python's standard `imaplib` + `email` (no extra deps)
- **Quick presets** — One-click setup for QQ, 163, Gmail, Outlook, and more
- **LLM-powered** — Groups emails by importance (important / normal / notifications) with one-line summaries
- **Fallback** — Plain HTML list when no LLM is configured
- Connection testing and scheduled auto-generation

## Focus Timer App

A full-featured Pomodoro timer to help you stay productive.

- **Timer** — Large ring countdown with start / pause / reset / skip controls
- **Customizable** — Set focus, break, and long-break durations
- **Task tags** — Label sessions (coding, reading, writing…) for tracking
- **Statistics** — Today's stats, daily trend chart (CSS bars), and tag distribution
- **History** — Browse completed sessions, all stored locally
- Timer runs in the frontend; completed sessions are saved to the backend

## Custom Apps

Create your own automated applications powered by the full nanobot agent.

- **Prompt Template** — Define a task in natural language with `{{variable}}` placeholders for dynamic parts
- **Parameter System** — Each variable becomes a configurable parameter (text, number, time, etc.)
- **Agent-powered** — Every run goes through the full nanobot agent loop with MCP tools, web search, and more
- **Save from Chat** — Click "Save as App" on any bot reply to turn that conversation into a reusable app
- **Create from Scratch** — Or open the creation wizard directly from the App Center
- **Scheduling** — Optional daily schedule with configurable run time
- **Reports** — Each run saves a dated report you can browse later

Unlike the built-in apps (which use optimised direct pipelines), custom apps leverage the full agent capabilities for maximum flexibility.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.10+ | Required |
| **pywebview** | — | Included in `requirements.txt`. Uses platform-native webview (EdgeWebView2 on Windows, WebKit on macOS/Linux). Falls back to browser mode if unavailable |
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

A native desktop window will open. If `pywebview` is not installed, it will fall back to browser mode.

## Tech Stack

| Layer | Technology |
|---|---|
| Native window | pywebview (platform-native webview) |
| Backend API | Flask |
| Frontend | Vanilla HTML / CSS / JS |
| Markdown rendering | marked.js |
| Code highlighting | highlight.js |
| AI engine | nanobot-ai |
| LLM routing | litellm (auto provider detection) |
| Web search | Brave API / Bing / DuckDuckGo (auto-fallback) |

## Project Structure

```
myai/
├── app.py              # Main app: Flask backend + pywebview window
├── requirements.txt    # Python dependencies
├── README.md           # English documentation
├── README_CN.md        # Chinese documentation
├── apps/
│   ├── __init__.py
│   ├── llm_utils.py    # Shared LLM call utility
│   ├── daily_digest.py # Today's Reading app: full pipeline
│   ├── web_monitor.py  # Web Monitor app: page change detection
│   ├── email_summary.py# Email Summary app: IMAP + LLM summary
│   ├── focus_timer.py  # Focus Timer app: session persistence + stats
│   └── custom_app.py   # Custom App framework: CRUD, templates, reports
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
