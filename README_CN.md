<div align="center">

# 🌀 MyxAI Desk

### 你的桌面 AI 私享会

每天 5 分钟，AI 帮你整理思路、讲透重点、继续深挖。

不只是聊天工具。
是一个真正懂你、陪你持续推进的桌面助手。

[English](README.md) · [快速开始](#-3-分钟上手) · [为什么不一样](#-为什么它不一样)

</div>

---

## 😵‍💫 你可能正在经历

- 每天打开十几个网页，却很难形成系统认知。
- 和 AI 聊了很多，但第二天就忘了。
- 项目推进中，总是陷入局部细节。
- 想跟上趋势，但没时间一篇一篇看。
- 邮箱塞满了，花大量时间才能找到真正重要的。

**如果有一个 AI 助手，真的在关注你每天在做什么——然后帮你理清头绪呢？**

---

## ✨ MyxAI 帮你做什么

### 🎯 每日私享会 — 你的私人资讯策展人

每天，MyxAI 自动读取你的浏览记录和近期对话，
分析你真正关心什么，全网搜索最有价值的内容，
生成一份**只属于你的私享会**。

- **理解你的上下文** — 不只是关键词，而是真实的兴趣方向（工作 / 学习 / 生活）
- **帮你搜** — 找到你自己可能错过的新鲜内容
- **越用越懂你** — 追踪你的兴趣变化趋势，一周比一周精准
- **一键深入** — 看到感兴趣的？点击直接进入深度对话
- **省 token** — 结构化 JSON 输出 + 模板渲染，LLM 成本降低 60-70%

> 不装插件。不用手动输入。打开就有。

### 📧 邮件简报 — 你的收件箱，一页看完

IMAP 连接邮箱。不再逐封罗列，MyxAI 生成一份**分类简报**：

- 按主题归类（需要回复、项目进展、知识分享、通知订阅等）
- 每个分类一句话总结
- 提取关键要点
- 明确标出需要你关注和回复的事项

> 50 封邮件 → 一页扫完，30 秒掌握全局。

### 💬 有记忆的对话

自然地和 AI 聊天——你们的对话会成为它理解你的一部分。

### 📊 统一报告中心

所有报告集中在一个页面 — 每日私享会、邮件简报、自定义应用。按时间范围筛选、标记已读、在页面内直接浏览，不用来回切换。

### 📈 用量统计

LLM token 消耗和搜索 API 用量一目了然，按天展示柱状图，精确掌握开销。

### 🔍 网页监控

追踪任何网页变化。有更新就提醒你——还能用 AI 总结到底变了什么。

### ⏱️ 专注计时

完整的番茄钟，支持任务标签和统计图表——专注工作，量化习惯。

### 🧩 自定义应用

把任何对话变成可重复执行的应用。你的 AI，你的工作流。

---

## 🔥 为什么它不一样

| | 普通 AI 聊天 | MyxAI Desk |
|---|---|---|
| **上下文** | 每次从零开始 | 知道你最近在关注什么 |
| **内容** | 你问它才答 | 主动帮你找到值得看的 |
| **连续性** | 对话用完即弃 | 兴趣持续积累 |
| **深度** | 表面回答 | 一键深入任何话题 |
| **主动性** | 等你来问 | 每天自动准备好你的私享会 |
| **效率** | token 花在格式上 | 结构化输出，精打细算 |

---

## 🚀 3 分钟上手

```bash
# 1. 克隆 & 安装
git clone https://github.com/your-org/myxai-desk.git
cd myxai-desk
pip install -r requirements.txt

# 2. 启动
python app.py
```

桌面窗口自动打开。在设置里配置 LLM API Key，就可以用了。

> 首次使用？应用会引导你完成初始化。

---

## 🧠 核心能力一览

| | |
|---|---|
| 🎯 **每日私享会** | 基于真实行为的 AI 资讯策展 |
| 📧 **邮件简报** | 分类归纳的收件箱摘要，突出关注事项 |
| 💬 **上下文对话** | 对话建立在你正在做的事情之上 |
| 📊 **报告中心** | 所有报告统一浏览，支持筛选和内联查看 |
| 📈 **用量统计** | Token 与搜索 API 消耗追踪 |
| 🔍 **网页监控** | AI 驱动的页面变化追踪与总结 |
| 🧩 **自定义应用** | 把任何 prompt 变成可复用的自动化工作流 |

---

## 🏗️ 技术细节

给好奇架构的开发者：

| 层 | 技术 |
|---|---|
| 桌面窗口 | pywebview（原生窗口） |
| 后端 | Flask API |
| 前端 | 原生 HTML/CSS/JS |
| AI 引擎 | nanobot + litellm |
| 全网搜索 | 百度 / Brave API |
| 主题 | Catppuccin Mocha |

<details>
<summary>项目结构</summary>

```
myai/
├── app.py              # Flask 后端 + pywebview 窗口
├── requirements.txt
├── apps/
│   ├── daily_digest.py # 每日私享会 pipeline
│   ├── email_summary.py# 邮件简报（IMAP + AI）
│   ├── web_monitor.py  # 网页变化检测
│   ├── focus_timer.py  # 番茄钟
│   ├── custom_app.py   # 自定义应用框架
│   ├── web_search.py   # 多引擎搜索 + 配额管理
│   └── llm_utils.py    # 共享 LLM 工具 + token 追踪
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

</details>

<details>
<summary>LLM 提供商配置</summary>

大多数提供商（DashScope / DeepSeek / Moonshot / SiliconFlow / Groq）都支持 OpenAI 兼容端点。在 **设置 → API 密钥 → openai** 中配置：

| 提供商 | API Base |
|---|---|
| DashScope（通义千问） | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot（Kimi） | `https://api.moonshot.cn/v1` |
| SiliconFlow（硅基流动） | `https://api.siliconflow.cn/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

</details>

---

<div align="center">

**让 AI 成为真正陪伴你思考的桌面助手。**

⭐ 如果你觉得有共鸣，给个 Star 吧。

</div>
