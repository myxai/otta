<div align="center">

# 🌀 MyxAI Desk

### Your Desktop AI That Actually Knows You

Every day, it reads what you browse, understands what you care about,
and delivers a private briefing just for you — with one click to go deeper.

Not just another chatbot. A thinking companion that grows with you.

[中文](README_CN.md) · [Quick Start](#-3-minutes-to-get-started) · [Why It's Different](#-why-its-different)

</div>

---

## 😵‍💫 Sound Familiar?

- You open dozens of tabs every day — but nothing sticks.
- You chat with AI about ideas — then forget them by tomorrow.
- You're working on a project — but keep getting lost in the details.
- You want to stay on top of trends — without spending hours reading.
- Your inbox is flooded — you waste time scanning for what actually matters.

**What if an AI assistant actually paid attention to what you're doing — and helped you make sense of it?**

---

## ✨ What MyxAI Does

### 🎯 Daily Briefing — Your Private Curator

Every day, MyxAI locally reads your browsing history and recent AI conversations,
figures out what you truly care about, searches the web for the best content,
and delivers a **personalised briefing** you actually want to read.

> 🔒 All data processing happens locally on your device. Browsing history is never uploaded to any server.

- **Understands your context** — not just keywords, but your real interests across work, study, and life
- **Searches the web for you** — finds fresh, relevant content you'd miss on your own
- **Gets smarter over time** — tracks how your interests evolve week by week
- **One-click deep dive** — see something interesting? Click to explore it in a focused conversation
- **Token-efficient** — structured JSON output + template rendering, 60-70% less LLM cost

> No plugins. No manual input. It just works.

### 📧 Email Briefing — Your Inbox, Distilled

Connect via IMAP. Instead of listing every email, MyxAI generates a **categorised briefing**:

- Groups emails by theme (action needed, project updates, newsletters, etc.)
- Summarises each category in one sentence
- Highlights what deserves your attention
- Tells you exactly what needs a reply

> 50 emails → one page you can scan in 30 seconds.

### 💬 Smart Chat with Memory

Chat naturally with AI — your conversations become part of its understanding of you.

### 📊 Unified Reports Hub

All reports in one place — Daily Briefing, Email Briefing, Custom Apps. Filter by time range, mark as read, browse inline without switching pages.

### 📈 Usage Statistics

Track your LLM token consumption and search API usage with daily charts. Know exactly what you're spending.

### 🔍 Web Monitor

Track any web page for changes. Get notified when something updates — with an AI summary of what changed.

### ⏱️ Focus Timer

Full Pomodoro timer with task tags and beautiful stats — stay productive and track your focus habits.

### 🧩 Custom Apps

Turn any conversation into a reusable, scheduled app — focused on web search and content generation tasks. Your AI, your workflow.

### 🛡️ Safety Architecture

Safety is MyxAI's first design principle, enforced across every layer of conversations and apps.

- **Zero deletion** — no file is ever permanently deleted anywhere in the system. All "deletes" move to a trash folder (`~/.nanobot/trash/`), fully recoverable
- **Execution confirmation** — any local file system operation in chat requires the AI to show an execution plan first; only proceeds after explicit user approval
- **Dangerous operations refused** — destructive actions (delete files, format disks, empty trash, etc.) are refused even if the user explicitly requests them
- **Tool-level interception** — dangerous commands are intercepted in real-time before execution
- **Custom app sandbox** — custom apps can only use web search tools, no local operations allowed
- **Local processing** — all data processing happens locally on your device; nothing is uploaded to any server

---

## 🔥 Why It's Different

| | Typical AI Chat | MyxAI Desk |
|---|---|---|
| **Context** | Starts fresh every time | Knows what you've been exploring |
| **Content** | You have to ask | It finds what matters to you |
| **Continuity** | Conversations are disposable | Your interests accumulate over time |
| **Depth** | Surface-level answers | One-click deep dive into any topic |
| **Proactivity** | Waits for you | Delivers your briefing automatically |
| **Efficiency** | Burns tokens on formatting | Structured output, minimal waste |

---

## 🚀 3 Minutes to Get Started

```bash
# 1. Clone & install
git clone https://github.com/your-org/myxai-desk.git
cd myxai-desk
pip install -r requirements.txt

# 2. Launch
python app.py
```

A native desktop window opens. Configure your LLM API key in Settings, and you're ready.

> First time? The app will walk you through setup.

---

## 🧠 Core Capabilities

| | |
|---|---|
| 🎯 **Daily Briefing** | AI-curated content based on your real behaviour |
| 📧 **Email Briefing** | Categorised inbox summary with action highlights |
| 💬 **Contextual Chat** | Conversations that build on what you're doing |
| 📊 **Reports Hub** | Unified view of all reports with inline browsing |
| 📈 **Usage Stats** | Token & search API consumption tracking |
| 🔍 **Web Monitor** | Track page changes with AI-powered summaries |
| 🛡️ **Safety** | Zero deletion, execution confirmation, danger interception, app sandbox |
| 🧩 **Custom Apps** | Web search + content generation reusable workflows |

---

## 🏗️ Under the Hood

For developers curious about the architecture:

| Layer | Tech |
|---|---|
| Desktop | pywebview (native window) |
| Backend | Flask API |
| Frontend | Vanilla HTML/CSS/JS |
| AI Engine | nanobot + litellm |
| Search | Baidu / Brave API |
| Theme | Catppuccin Mocha |

<details>
<summary>Project Structure</summary>

```
myai/
├── app.py               # Flask backend + pywebview + safety interception
├── requirements.txt
├── apps/
│   ├── daily_digest.py  # Daily Briefing pipeline
│   ├── email_summary.py # Email Briefing (IMAP + AI)
│   ├── web_monitor.py   # Page change detection
│   ├── custom_app.py    # Custom app framework
│   ├── web_search.py    # Multi-engine search + quota
│   ├── safe_fs.py       # Safe file operations (zero deletion, trash-based)
│   └── llm_utils.py     # Shared LLM utils + token tracking
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

</details>

<details>
<summary>LLM Provider Setup</summary>

Most providers (DashScope, DeepSeek, Moonshot, SiliconFlow, Groq) offer OpenAI-compatible endpoints. Configure in **Settings → API Keys → openai**:

| Provider | API Base |
|---|---|
| DashScope (Qwen) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot (Kimi) | `https://api.moonshot.cn/v1` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

</details>

---

<div align="center">

**Make AI a thinking companion that sits on your desktop.**

⭐ Star this repo if it resonates with you.

</div>
