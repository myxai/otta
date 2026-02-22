# 🌀 MyxAI Desk 

基于 [nanobot](https://github.com/HKUDS/nanobot) 的桌面可视化客户端。

[English](README.md)

## 功能

- **对话** — 与 nanobot AI 助手实时聊天，支持 Markdown 渲染和代码高亮
- **应用中心** — 可扩展的应用管理；安装、配置和管理自动化任务
  - **今日私读** — 基于浏览器历史和对话内容的 AI 个人兴趣推荐引擎
  - **网页监控** — 跟踪网页变化，支持哈希对比和 LLM 智能摘要两种模式
  - **邮件摘要** — 通过 IMAP 连接邮箱，AI 生成每日邮件摘要
  - **专注计时** — 完整番茄钟，自定义时长、任务标签、统计图表
  - **自定义应用** — 将任意 nanobot 对话转化为可重复执行的定时应用
- **设置** — 可视化配置 API 密钥、模型参数、MCP 工具服务、频道开关等
- **状态** — 一览当前系统状态：提供商、频道、模型配置、MCP 工具、反馈案例
- **网关** — 一键启停 nanobot gateway，连接 Telegram / Discord / 飞书等平台
- **MCP 集成** — 通过 MCP 协议连接外部工具服务（如 Playwright 浏览器自动化）
- **中英双语** — 界面支持中文 / English 切换，默认跟随系统语言

## 今日私读

自动分析浏览器历史**和 nanobot 对话内容**，识别你的真实兴趣，全网搜索高质量内容，生成个性化推荐报告。

**工作流程：**

1. **采集** — 读取 Chrome / Edge 浏览历史（仅标题和 URL）**+ 近期 nanobot 对话内容**（你和 AI 讨论过的主题）
2. **分析** — LLM 综合两个来源识别真实兴趣并分类（工作 / 学习 / 生活）
3. **搜索** — 生成语义完整的搜索词，调用搜索 API（百度 / Brave，支持每日额度追踪）
4. **策展** — LLM 从搜索结果中精选最优内容，生成带真实链接的 HTML 卡片报告

**设计特点：**

- 无需安装浏览器插件，直接读取本地历史数据库
- 综合浏览行为和 AI 对话主题，更深入理解兴趣
- AI 驱动的兴趣提取（LLM 不可用时自动降级为规则方案）
- 纯 API 搜索（百度 / Brave），实时统计每日调用次数，支持免费额度限制
- 结构化 HTML 卡片报告，美观易读
- 支持定时自动生成或手动触发
- 兴趣预览功能，快速查看分析结果

## 网页监控

监控指定网页的变化，有更新时自动提醒。

- **哈希模式** — 提取页面正文文本，SHA-256 对比，速度快，无 LLM 成本
- **LLM 模式** — 用 AI 总结新旧版本之间具体发生了什么变化
- 可配置检查间隔（默认 30 分钟）
- 变化历史记录，带时间戳和摘要
- 支持手动检查和定时自动检查

## 邮件摘要

通过 IMAP 连接邮箱，AI 生成简洁的每日邮件摘要。

- **内置 IMAP** — 使用 Python 标准库 `imaplib` + `email`，无需额外依赖
- **快速预设** — 一键填入 QQ邮箱 / 163 / Gmail / Outlook 等常见邮箱配置
- **LLM 驱动** — 按重要程度分组（重要 / 普通 / 通知），每封一句话摘要
- **降级方案** — 无 LLM 时生成简单 HTML 邮件列表
- 支持连接测试和定时自动生成

## 专注计时

完整的番茄钟工作法，帮助你保持高效专注。

- **计时器** — 大圆环倒计时，开始 / 暂停 / 重置 / 跳过
- **自定义** — 设置专注、休息、长休息时长
- **任务标签** — 为每次专注标记类别（编程、阅读、写作…）
- **统计面板** — 今日数据、每日趋势柱状图（纯 CSS）、按标签分布
- **历史记录** — 浏览已完成的专注会话，数据本地存储
- 计时器在前端运行，完成后自动保存到后端

## 自定义应用

将 nanobot 的对话能力转化为可重复执行的自动化应用。

- **Prompt 模板** — 用自然语言描述任务，用 `{{变量名}}` 标记动态部分
- **参数系统** — 每个变量自动成为可配置参数（文本、数值、时间等）
- **Agent 驱动** — 每次执行都经过完整的 nanobot Agent 循环（MCP 工具、搜索等全部可用）
- **从对话保存** — 在聊天界面的 bot 回复上点击「💾 保存为应用」，一键转化
- **从零创建** — 也可以在应用中心直接点击「新建自定义应用」手写模板
- **定时调度** — 可选每日定时执行，自定义执行时间
- **执行报告** — 每次运行自动保存报告，支持历史浏览

与内置应用（使用优化的直连 pipeline）不同，自定义应用利用 Agent 的完整能力，灵活性最强。

## 环境要求

| 环境 | 版本 | 说明 |
|---|---|---|
| **Python** | 3.10+ | 必需 |
| **pywebview** | — | 已包含在 `requirements.txt` 中。使用平台原生 webview（Windows 上为 EdgeWebView2，macOS/Linux 上为 WebKit）。未安装时自动回退为浏览器模式 |
| **Node.js**（可选） | 18+ | 仅在使用 MCP 工具服务（如 Playwright 浏览器自动化）时需要。[下载](https://nodejs.org/) |
| **LLM API Key** | — | 至少配置一个提供商的密钥（如 DashScope / OpenAI / DeepSeek / Anthropic），启动后在设置页面填写 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 首次使用

如果尚未初始化过 nanobot，应用会引导你完成初始化。也可以手动执行：

```bash
nanobot onboard
```

### 3. 启动桌面应用

```bash
python app.py
```

将打开一个原生桌面窗口。如果未安装 `pywebview`，会自动回退到浏览器模式。

## 技术栈

| 层 | 技术 |
|---|---|
| 原生窗口 | pywebview（平台原生 webview） |
| 后端 API | Flask |
| 前端 | 原生 HTML / CSS / JS |
| Markdown 渲染 | marked.js |
| 代码高亮 | highlight.js |
| AI 引擎 | nanobot-ai |
| LLM 路由 | litellm（自动识别 provider） |
| 全网搜索 | 百度千帆 API / Brave Search API（支持每日额度管理） |

## 项目结构

```
myai/
├── app.py              # 主程序：Flask 后端 + pywebview 窗口
├── requirements.txt    # Python 依赖
├── README.md           # 英文文档
├── README_CN.md        # 中文文档
├── apps/
│   ├── __init__.py
│   ├── llm_utils.py    # 共享 LLM 调用工具
│   ├── daily_digest.py # 今日私读：完整 pipeline
│   ├── web_monitor.py  # 网页监控：页面变化检测
│   ├── email_summary.py# 邮件摘要：IMAP + LLM 摘要
│   ├── focus_timer.py  # 专注计时：会话持久化 + 统计
│   ├── custom_app.py   # 自定义应用：CRUD、模板引擎、报告存储
│   └── web_search.py   # 纯 API 搜索：百度 / Brave，含每日额度追踪
└── frontend/
    ├── index.html      # 前端页面
    ├── style.css       # 样式 (Catppuccin Mocha 暗色主题)
    └── app.js          # 前端逻辑 (含 i18n)
```

## 配置

所有配置存储在 `~/.nanobot/config.json`，可以通过桌面应用的「设置」页面进行可视化编辑。

### 常用配置

- **模型** — 在设置页面填写模型名称（如 `qwen-plus`、`deepseek-chat`、`claude-opus-4-5`）
- **API Key** — 在设置页面的「API 密钥」部分填写对应提供商的密钥
- **MCP 服务** — 在「MCP 工具服务」部分添加工具服务（如 Playwright）
- **频道** — 在设置页面切换频道开关，详细频道配置请使用高级 JSON 编辑器
- **语言** — 在侧边栏或设置页面切换中文 / English

### 模型提供商配置建议

大多数 LLM 提供商（DashScope / DeepSeek / Moonshot / SiliconFlow / Groq 等）都提供了 **OpenAI 兼容**的 API 端点。建议统一配置在 **OpenAI** 提供商下：

1. 进入 **设置 → API 密钥 → openai**
2. 填写提供商给你的 **API Key**
3. 将 **API Base** 设置为对应提供商的 OpenAI 兼容端点，例如：

| 提供商 | API Base |
|---|---|
| DashScope（通义千问） | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot（Kimi） | `https://api.moonshot.cn/v1` |
| SiliconFlow（硅基流动） | `https://api.siliconflow.cn/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

4. 在**模型名称**中填写要使用的模型（如 `qwen-plus`、`deepseek-chat`）

这种方式兼容性最好，避免了各厂商 SDK 的差异问题。
