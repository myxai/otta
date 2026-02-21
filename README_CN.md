# nanobot Desktop

基于 [nanobot](https://github.com/HKUDS/nanobot) 的 Windows 桌面可视化客户端。

[English](README.md)

## 功能

- **对话** — 与 nanobot AI 助手实时聊天，支持 Markdown 渲染和代码高亮
- **应用中心** — 可扩展的应用管理；安装、配置和管理自动化任务
  - **推荐日报** — 基于浏览器历史的 AI 个人兴趣推荐引擎
- **设置** — 可视化配置 API 密钥、模型参数、MCP 工具服务、频道开关等
- **状态** — 一览当前系统状态：提供商、频道、模型配置、MCP 工具、反馈案例
- **网关** — 一键启停 nanobot gateway，连接 Telegram / Discord / 飞书等平台
- **MCP 集成** — 通过 MCP 协议连接外部工具服务（如 Playwright 浏览器自动化）
- **中英双语** — 界面支持中文 / English 切换，默认跟随系统语言

## 推荐日报

自动分析浏览器历史，识别你的真实兴趣，全网搜索高质量内容，生成个性化推荐报告。

**工作流程：**

1. **采集** — 读取 Chrome / Edge 浏览历史（仅标题和 URL，不读取页面内容）
2. **分析** — LLM 识别真实兴趣并分类（工作 / 学习 / 生活）
3. **搜索** — 生成语义完整的搜索词，全网搜索（Brave → Bing → DuckDuckGo 自动降级）
4. **策展** — LLM 从搜索结果中精选最优内容，生成带真实链接的 HTML 卡片报告

**设计特点：**

- 无需安装浏览器插件，直接读取本地历史数据库
- AI 驱动的兴趣提取（LLM 不可用时自动降级为规则方案）
- 多搜索引擎自动降级（Brave API → Bing → DuckDuckGo）
- 结构化 HTML 卡片报告，美观易读
- 支持定时自动生成或手动触发
- 兴趣预览功能，快速查看分析结果

## 环境要求

| 环境 | 版本 | 说明 |
|---|---|---|
| **Python** | 3.10+ | 必需 |
| **Edge WebView2 Runtime** | — | Windows 10 (2004+) / 11 已预装。若缺失请[下载安装](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |
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

将打开一个原生 Windows 窗口。如果未安装 `pywebview`，会自动回退到浏览器模式。

## 技术栈

| 层 | 技术 |
|---|---|
| 原生窗口 | pywebview (Edge WebView2) |
| 后端 API | Flask |
| 前端 | 原生 HTML / CSS / JS |
| Markdown 渲染 | marked.js |
| 代码高亮 | highlight.js |
| AI 引擎 | nanobot-ai |
| LLM 路由 | litellm（自动识别 provider） |
| 全网搜索 | Brave API / Bing / DuckDuckGo（自动降级） |

## 项目结构

```
myai/
├── app.py              # 主程序：Flask 后端 + pywebview 窗口
├── requirements.txt    # Python 依赖
├── README.md           # 英文文档
├── README_CN.md        # 中文文档
├── apps/
│   ├── __init__.py
│   └── daily_digest.py # 推荐日报：完整 pipeline
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
