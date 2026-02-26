/* ===================================================================
   MyxAI Desk — Frontend Logic
   =================================================================== */

// ── API token guard (localhost CSRF / DNS-rebinding protection) ────
// Token is injected by pywebview (window.__myxai_token) or via URL
// query param (?token=...) in browser-fallback mode.
(function _bootstrapToken() {
  if (window.__myxai_token) return;
  const p = new URLSearchParams(window.location.search);
  const t = p.get("token");
  if (t) {
    window.__myxai_token = t;
    // Strip token from URL to avoid leaking it in Referer headers
    const clean = window.location.pathname + window.location.hash;
    window.history.replaceState(null, "", clean);
  }
})();

function authHeaders(extra) {
  const h = extra ? Object.assign({}, extra) : {};
  if (window.__myxai_token) h["X-MyxAI-Token"] = window.__myxai_token;
  return h;
}

// ── Load i18n module ───────────────────────────────────────────────
// i18n.js will be loaded first via <script> tag in index.html

// ── Embedded i18n fallback (used if backend unavailable) ───────────────

const FALLBACK_I18N = {
  zh: {
    "nav.newChat":"新对话","nav.settings":"设置","nav.status":"状态","nav.gateway":"网关",
    "tasks.btn":"任务","tasks.today":"今日任务","tasks.planned":"待执行","tasks.running":"执行中","tasks.success":"已完成","tasks.failed":"失败","tasks.pendingCatchup":"待补偿","tasks.noTasks":"今日无任务","tasks.catchupNote":"补偿","tasks.runNow":"立即执行","tasks.triggered":"已触发执行","tasks.triggerFail":"触发失败",
    "setup.welcome":"欢迎使用 MyxAI Desk",
    "setup.install.title":"安装 nanobot","setup.install.desc":"在终端运行以下命令：",
    "setup.onboard.title":"初始化配置","setup.onboard.desc":"点击下方按钮自动初始化。","setup.onboard.btn":"初始化 nanobot",
    "setup.apikey.title":"配置 API Key","setup.apikey.desc":"前往「设置」页面填写您的 API Key。","setup.apikey.btn":"前往设置",
    "chat.ready":"MyxAI Desk 已就绪","chat.readyDesc":"输入消息开始对话，我可以帮你搜索信息、编写代码、管理文件等。",
    "chat.placeholder":"输入消息… (Enter 发送, Shift+Enter 换行)",
    "chat.you":"你","chat.noHistory":"暂无历史对话","chat.newChat":"新对话",
    "chat.rename":"重命名","chat.renameTitle":"修改对话标题","chat.renamePlaceholder":"输入新标题",
    "chat.regenerate":"重新回答",
    "chat.rated":"已评价","chat.thankFeedback":"感谢反馈！","chat.willImprove":"已记录，会改进",
    "chat.askDislike":"可以说说哪里不满意吗？（可留空）",
    "chat.error":"错误: ","chat.requestFail":"请求失败: ",
    "chat.executing":"执行中…","chat.execDone":"执行完成","chat.steps":"步",
    "settings.title":"设置","settings.save":"保存配置",
    "settings.model":"模型设置","settings.modelName":"模型名称",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"最大工具迭代次数","settings.memoryWindow":"记忆窗口大小",
    "settings.apiKeys":"API 密钥",
    "settings.searchTools":"搜索与工具","settings.baiduKey":"百度搜索 API Key","settings.braveKey":"Brave Search API Key",
    "settings.quotaOnly":"仅使用免费额度","settings.usageToday":"今日已用","settings.quotaExhausted":"额度已用完",
    "settings.shellTimeout":"Shell 超时 (秒)","settings.restrictWorkspace":"限制工具在工作区内操作",
    "settings.channels":"频道",
    "settings.advancedJson":"高级 JSON 编辑","settings.toggleJson":"展开/折叠","settings.applyJson":"应用 JSON",
    "settings.saved":"配置已保存","settings.saveFail":"保存失败","settings.loadFail":"加载配置失败",
    "settings.jsonApplied":"JSON 已应用到表单","settings.jsonError":"JSON 格式错误: ",
    "settings.language":"界面语言","settings.langAuto":"跟随系统","settings.langZh":"中文","settings.langEn":"English",
    "mcp.title":"MCP 工具服务","mcp.desc":"连接外部 MCP 服务器，扩展 Agent 的工具能力（如浏览器、数据库等）。",
    "mcp.empty":"暂未配置 MCP 服务","mcp.addServer":"+ 添加服务",
    "mcp.pickTitle":"选择 MCP 服务类型","mcp.serverName":"服务名称","mcp.delete":"✕ 删除",
    "mcp.argsHelp":"参数每行一个","mcp.argsPlaceholder":"每行一个参数，或 JSON 数组","mcp.cancel":"取消",
    "mcp.presetPlaywright":"Playwright (浏览器)","mcp.presetFilesystem":"Filesystem (文件系统)",
    "mcp.presetStdio":"自定义 Stdio","mcp.presetHttp":"自定义 HTTP",
    "status.title":"系统状态","status.refresh":"刷新","status.loading":"加载中…","status.loadFail":"加载失败: ",
    "status.configFile":"配置文件","status.workspace":"工作区","status.currentModel":"当前模型",
    "status.providers":"LLM 提供商","status.configured":"已配置","status.notConfigured":"未配置",
    "status.channels":"频道状态","status.enabled":"已启用","status.disabled":"未启用",
    "status.mcpTools":"MCP 工具服务","status.cases":"反馈案例库",
    "status.mcpConnected":"已连接","status.mcpNotConnected":"未连接","status.mcpNoTools":"无工具注册",
    "status.mcpTest":"测试连接","status.mcpReconnect":"重新连接","status.mcpTesting":"测试中…","status.mcpReconnecting":"连接中…",
    "status.mcpLog":"诊断日志","status.mcpRegisteredTools":"已注册工具",
    "status.positiveCases":"正面案例 (👍)","status.negativeCases":"负面案例 (👎)",
    "status.recentPositive":"最近正面","status.recentNegative":"最近负面",
    "gw.title":"网关控制","gw.stopped":"网关已停止","gw.running":"网关运行中",
    "gw.stoppedDesc":"启动网关以连接 Telegram、Discord 等平台","gw.runningDesc":"网关正在处理来自各频道的消息",
    "gw.start":"启动网关","gw.stop":"停止网关","gw.logs":"网关日志",
    "gw.started":"网关已启动","gw.startFail":"启动失败","gw.stopFail":"停止失败","gw.stoppedMsg":"网关已停止",
    "common.onboardOk":"初始化成功！","common.onboardFail":"初始化失败",
    "voice.ttsToggle":"语音提醒","voice.listening":"正在聆听…","voice.unsupported":"浏览器不支持语音输入",
    "voice.ttsOn":"语音提醒已开启","voice.ttsOff":"语音提醒已关闭",
    "security.mode":"安全模式:","security.switched":"安全模式已切换为","security.switchFail":"切换失败",
    "security.modeName.Observer":"观察模式","security.modeName.Assistant":"协作模式",
    "security.modeName.Operator":"操作模式","security.modeName.Developer":"开发模式",
    "security.Observer":"观察模式 — 可智能安全新增","security.Assistant":"协作模式 — 可智能安全修改",
    "security.Operator":"操作模式 — 可智能安全删除/恢复","security.Developer":"开发模式 — 可执行所有操作（高风险）",
    "security.opt.Observer":"观察模式 — 可智能安全新增","security.opt.Assistant":"协作模式 — 可智能安全修改",
    "security.opt.Operator":"操作模式 — 可智能安全删除/恢复","security.opt.Developer":"开发模式 — 可执行所有操作（高风险）",
    "security.shortDesc.Observer":"可智能安全新增","security.shortDesc.Assistant":"可智能安全修改",
    "security.shortDesc.Operator":"可智能安全删除/恢复","security.shortDesc.Developer":"可执行所有操作（高风险）",
    "security.devRequired":"开发模式只能通过系统设置开启",
    "security.devEnable":"启用开发模式","security.devDisable":"关闭开发模式",
    "security.devExpiry":"失效策略","security.devExpiry.on_app_close":"关闭应用后失效",
    "security.devExpiry.duration_1h":"1小时后失效","security.devExpiry.duration_24h":"24小时后失效",
    "security.devActive":"开发模式已启用","security.devExpired":"开发模式已过期",
    "security.devRemaining":"剩余时间",
    "settings.auditDesc":"查看操作审计记录和可撤销操作历史。",
    "settings.auditOpen":"打开审计日志",
    "security.devCard.title":"🛡️ 开发模式 — 可执行所有操作（高风险）",
    "security.devCard.desc":"开发模式可执行所有操作，包括文件删除、命令执行、网络外传等高风险操作。仅限受信任环境使用，必须设置失效策略。",
    "security.devCard.btn":"⚙️ 配置开发模式",
    "security.devCard.warning":"开发模式 — 可执行所有操作（高风险），包括文件删除、系统命令、数据外传等。请选择失效策略以控制风险。",
    "security.devClose":"关闭","security.devUnit.min":"分钟","security.devDisabled":"开发模式已关闭",
    "nav.audit":"审计","audit.title":"审计日志","audit.verify":"验证链完整性","audit.export":"导出",
    "audit.recentActions":"最近可撤销操作","audit.empty":"暂无审计记录","audit.chainValid":"审计链完整性验证通过",
    "audit.chainInvalid":"审计链验证失败","audit.undoSuccess":"撤销成功","audit.undoFail":"撤销失败",
    "audit.noUndo":"暂无可撤销操作",
    "privacy.title":"隐私与个性化","privacy.subtitle":"你掌控数据，我负责更贴合的结果。",
    "privacy.dataTitle":"用这些信息，让结果更顺手",
    "privacy.browserHistory":"浏览记录","privacy.browserHint":"更贴近你最近关注的内容",
    "privacy.chatHistory":"对话记录","privacy.chatHint":"更贴近你正在思考的问题",
    "privacy.fileHistory":"文件变更","privacy.fileHint":"更贴近你当前的工作进展",
    "privacy.watchPaths":"监控文件夹","privacy.watchPathsHelp":"输入要监控的文件夹路径，每行一个。例如：D:\\Projects",
    "privacy.retention":"保留天数","privacy.generate":"生成个性化","privacy.clear":"清空个性化",
    "privacy.analysisDays":"分析时长（天）","privacy.analysisDaysHelp":"生成画像时分析最近 N 天的数据，不保存历史记录",
    "privacy.localNote":"所有数据默认仅在本地处理。",
    "privacy.usageTitle":"画像使用范围",
    "privacy.personaInDigest":"允许画像增强 AI 回复","privacy.personaInDigestHint":"画像仅注入系统提示词，对话内容中不会出现",
    "privacy.personaUsageNote":"开启后，AI 会根据你的背景和兴趣给出更贴合的回复，但画像内容不会出现在任何对话消息中。",
    "privacy.effectTitle":"当前个性化效果",
    "privacy.stablePersona":"稳定画像","privacy.recentSnapshot":"近期兴趣",
    "privacy.statusOff":"当前处于标准模式，不使用历史信息。",
    "privacy.statusOn":"个性化已启用，会随着使用逐步优化。",
    "privacy.advanced":"高级设置",
    "privacy.generating":"正在生成...","privacy.generated":"个性化已生成","privacy.cleared":"个性化已清空","privacy.saved":"设置已保存",
    "privacy.copied":"已复制","privacy.editSaved":"已保存",
    "nav.reports":"报告","nav.apps":"应用",
    "reports.title":"报告","reports.unread":"未读","reports.24h":"24小时","reports.3d":"3天","reports.7d":"7天","reports.30d":"30天","reports.all":"全部",
    "reports.empty":"暂无报告","reports.allRead":"全部已读，去看看其他时间段吧","reports.viewReport":"查看",
    "reports.markAllRead":"全部已读","reports.delete":"删除","reports.deleteOk":"已删除","reports.deleteFail":"删除失败",
    "nav.stats":"统计","stats.todayPrefix":"今日","stats.tokenTitle":"Token 消耗","stats.searchTitle":"搜索 API 调用",
    "stats.rangeTotal":"累计","stats.tokenTip":"今日 LLM Token 消耗量","stats.searchTip":"今日各搜索引擎用量 / 额度",
    "stats.categoryTitle":"分类消耗","stats.categoryPieTitle":"消耗构成","stats.categoryBarTitle":"平均单次消耗","stats.catChat":"对话","stats.avgTokens":"平均 Token","stats.noData":"暂无数据，使用后自动生成",
    "apps.title":"应用中心","apps.search":"搜索应用…","apps.back":"返回",
    "apps.sortRecommended":"推荐","apps.sortFrequency":"使用频率","apps.sortCreated":"创建时间","apps.sortName":"名称",
    "apps.installed":"已安装","apps.notInstalled":"未安装","apps.comingSoon":"即将推出",
    "apps.install":"安装","apps.uninstall":"卸载","apps.configure":"配置","apps.viewReports":"报告",
    "apps.enabled":"已启用","apps.disabled":"已停用",
    "apps.enable":"启用","apps.disable":"停用",
    "apps.installOk":"应用安装成功","apps.uninstallOk":"应用已卸载",
    "apps.installFail":"安装失败","apps.uninstallFail":"卸载失败",
    "apps.version":"版本","apps.author":"作者",
    "digest.title":"每日私享","digest.subtitle":"你的私人资讯策展人——每天精选最值得关注的内容",
    "digest.privacyNote":"🔒 浏览记录仅在本地读取和分析，不会上传至任何服务器。",
    "digest.status":"状态","digest.config":"配置",
    "digest.browser":"浏览器","digest.browserAuto":"自动检测","digest.browserChrome":"Chrome","digest.browserEdge":"Edge",
    "digest.historyHours":"历史范围（小时）","digest.scheduleTime":"每日生成时间",
    "digest.pushNotification":"弹窗提醒","digest.pushEmail":"邮箱推送",
    "digest.runNow":"立即生成","digest.running":"正在生成…","digest.saveConfig":"保存设置",
    "digest.configSaved":"设置已保存","digest.configFail":"保存失败",
    "digest.reports":"往期私享会","digest.noReports":"暂无报告",
    "digest.preview":"兴趣预览","digest.previewDesc":"快速分析当前浏览器历史中的兴趣分布（优先使用 AI 分析）",
    "digest.previewBtn":"预览兴趣","digest.previewLoading":"正在分析…",
    "digest.previewMethod":"分析方式","digest.previewRuleBased":"规则",
    "digest.work":"工作","digest.study":"学习","digest.life":"生活",
    "digest.rawCount":"原始记录","digest.filteredCount":"有效记录","digest.chatCount":"对话/消息","digest.keywordCount":"兴趣数","digest.searchResults":"搜索推荐",
    "digest.viewReport":"查看","digest.lastRun":"上次运行",
    "digest.generating":"正在为你准备私享会…","digest.generateOk":"今日私享会已准备好！",
    "digest.generateFail":"生成失败","digest.noHistory":"未找到浏览记录",
    "digest.latestReport":"最新私享会",
    "digest.explore":"一起探讨吧","digest.exploreFail":"探索失败",
    "email.title":"邮件简报","email.subtitle":"连接邮箱，AI 分类归纳生成邮件简报",
    "email.imapConfig":"IMAP 配置","email.host":"服务器","email.port":"端口",
    "email.user":"账号","email.password":"密码/授权码","email.ssl":"SSL",
    "email.folder":"文件夹","email.hours":"时间范围（小时）","email.maxEmails":"最大邮件数",
    "email.scheduleTime":"每日生成时间","email.presets":"快速填入",
    "email.testConn":"测试连接","email.testing":"测试中…","email.testOk":"连接成功",
    "email.testFail":"连接失败","email.runNow":"立即生成","email.running":"正在生成…",
    "email.saveConfig":"保存设置","email.configSaved":"设置已保存",
    "email.reports":"历史报告","email.noReports":"暂无报告","email.viewReport":"查看",
    "custom.title":"自定义应用","custom.create":"新建自定义应用","custom.createFromChat":"保存为应用",
    "custom.name":"应用名称","custom.icon":"图标","custom.template":"任务描述",
    "custom.templateHelp":"用 {{变量名}} 标记可变部分，如：搜索{{关键词}}的最新资讯",
    "custom.appType":"应用类型","custom.type.search":"网络搜索","custom.type.content":"内容生成",
    "custom.safetyNote":"应用可用能力由其安全模式决定",
    "custom.safetyModeHint":"当前模式: ",
    "custom.securityMode":"应用安全模式",
    "custom.securityModeInherit":"继承全局模式",
    "custom.securityModeHint":"选择高于全局的模式将获得更多能力，但也伴随更高风险",
    "custom.injectProfile":"注入个人画像","custom.injectProfileHelp":"自动附加您的兴趣话题、项目上下文到 Prompt 中，让应用更懂你",
    "custom.escalation.title":"安全模式升级确认",
    "custom.escalation.from":"当前全局模式",
    "custom.escalation.to":"应用请求模式",
    "custom.escalation.gained":"将获得的额外能力",
    "custom.escalation.warnings":"风险提示",
    "custom.escalation.confirm":"我已了解风险，确认升级",
    "custom.escalation.cancel":"取消",
    "custom.escalation.noEsc":"{target} 不超过全局 {global}，无需额外确认",
    "custom.escalation.risk.low":"低","custom.escalation.risk.medium":"中",
    "custom.escalation.risk.high":"高","custom.escalation.risk.critical":"极高",
    "custom.searchEngine":"搜索引擎",
    "custom.outputFmt":"输出格式","custom.fmt.report":"HTML报告","custom.fmt.notification":"通知","custom.fmt.text":"纯文本",
    "custom.schedule":"定时任务","custom.scheduleTime":"执行时间","custom.scheduleEnabled":"启用定时",
    "custom.schedMode":"频率","custom.sched.daily":"每天","custom.sched.weekly":"每周","custom.sched.monthly":"每月","custom.sched.interval":"间隔(天)",
    "custom.schedDow":"星期","custom.schedDom":"几号","custom.schedInterval":"间隔天数",
    "custom.weekdays":"周一,周二,周三,周四,周五,周六,周日",
    "custom.catchup":"智能补偿","custom.catchup.none":"不补偿（错过就算了）","custom.catchup.latest":"只补最近一次（推荐）","custom.catchup.all":"补齐错过的",
    "custom.catchup.noneHelp":"错过就算了，适合提醒类任务","custom.catchup.latestHelp":"下次打开应用会补执行一次","custom.catchup.allHelp":"适合日报/监控类任务，避免漏掉多天",
    "custom.catchup.window":"补偿窗口","custom.catchup.window24":"过去 24 小时","custom.catchup.window168":"过去 7 天",
    "custom.catchup.maxRuns":"一次最多补偿次数","custom.catchup.advanced":"高级选项",
    "custom.summary":"总结功能","custom.summaryEnabled":"启用总结","custom.summaryPrompt":"总结要求",
    "custom.summaryPromptHelp":"描述你希望如何总结历史数据，留空则使用默认总结",
    "custom.summaryRun":"生成总结","custom.summarySchedule":"定时总结",
    "custom.summaryFormat":"输出格式","custom.summaryRange":"分析范围",
    "custom.summaryFmtHtml":"HTML 报告","custom.summaryFmtText":"纯文本",
    "custom.summaryRangeDays":"天","custom.summaryRangeWeeks":"周","custom.summaryRangeMonths":"月",
    "custom.save":"保存应用","custom.saving":"保存中…","custom.saved":"应用已保存",
    "custom.run":"立即执行","custom.running":"执行中…","custom.runDone":"执行完成",
    "custom.runFail":"执行失败","custom.edit":"编辑","custom.delete":"删除",
    "custom.reports":"执行报告","custom.summaries":"总结报告","custom.noReports":"暂无报告","custom.viewReport":"查看",
    "custom.addGroup":"添加一组","custom.removeGroup":"移除","custom.group":"第 {n} 组",
    "custom.step1":"类型与任务","custom.step2":"定时与总结","custom.step3":"基本信息",
    "custom.next":"下一步","custom.prev":"上一步","custom.cancel":"取消",
    "custom.badge":"自定义",
  },
  en: {
    "nav.newChat":"New Chat","nav.settings":"Settings","nav.status":"Status","nav.gateway":"Gateway",
    "tasks.btn":"Tasks","tasks.today":"Today's Tasks","tasks.planned":"Planned","tasks.running":"Running","tasks.success":"Done","tasks.failed":"Failed","tasks.pendingCatchup":"Catch-up","tasks.noTasks":"No tasks today","tasks.catchupNote":"catch-up","tasks.runNow":"Run Now","tasks.triggered":"Task triggered","tasks.triggerFail":"Trigger failed",
    "setup.welcome":"Welcome to MyxAI Desk",
    "setup.install.title":"Install nanobot","setup.install.desc":"Run the following command in terminal:",
    "setup.onboard.title":"Initialize","setup.onboard.desc":"Click the button below to auto-initialize.","setup.onboard.btn":"Initialize nanobot",
    "setup.apikey.title":"Configure API Key","setup.apikey.desc":"Go to Settings page to enter your API Key.","setup.apikey.btn":"Go to Settings",
    "chat.ready":"nanobot is Ready","chat.readyDesc":"Type a message to start chatting. I can search the web, write code, manage files and more.",
    "chat.placeholder":"Type a message… (Enter to send, Shift+Enter for newline)",
    "chat.you":"You","chat.noHistory":"No chat history","chat.newChat":"New Chat",
    "chat.rename":"Rename","chat.renameTitle":"Rename chat","chat.renamePlaceholder":"Enter new title",
    "chat.regenerate":"Regenerate",
    "chat.rated":"Rated","chat.thankFeedback":"Thanks for the feedback!","chat.willImprove":"Noted, will improve",
    "chat.askDislike":"What could be better? (optional)",
    "chat.error":"Error: ","chat.requestFail":"Request failed: ",
    "chat.executing":"Executing…","chat.execDone":"Done","chat.steps":"steps",
    "settings.title":"Settings","settings.save":"Save",
    "settings.model":"Model Settings","settings.modelName":"Model Name",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"Max Tool Iterations","settings.memoryWindow":"Memory Window Size",
    "settings.apiKeys":"API Keys",
    "settings.searchTools":"Search & Tools","settings.baiduKey":"Baidu Search API Key","settings.braveKey":"Brave Search API Key",
    "settings.quotaOnly":"Free quota only","settings.usageToday":"Used today","settings.quotaExhausted":"Quota exhausted",
    "settings.shellTimeout":"Shell Timeout (sec)","settings.restrictWorkspace":"Restrict tools to workspace",
    "settings.channels":"Channels",
    "settings.advancedJson":"Advanced JSON Editor","settings.toggleJson":"Toggle","settings.applyJson":"Apply JSON",
    "settings.saved":"Configuration saved","settings.saveFail":"Save failed","settings.loadFail":"Failed to load config",
    "settings.jsonApplied":"JSON applied to form","settings.jsonError":"JSON syntax error: ",
    "settings.language":"Language","settings.langAuto":"System","settings.langZh":"中文","settings.langEn":"English",
    "mcp.title":"MCP Tool Services","mcp.desc":"Connect external MCP servers to extend Agent capabilities (e.g. browser, database).",
    "mcp.empty":"No MCP servers configured","mcp.addServer":"+ Add Server",
    "mcp.pickTitle":"Choose MCP Server Type","mcp.serverName":"Server Name","mcp.delete":"✕ Delete",
    "mcp.argsHelp":"One argument per line","mcp.argsPlaceholder":"One arg per line, or JSON array","mcp.cancel":"Cancel",
    "mcp.presetPlaywright":"Playwright (Browser)","mcp.presetFilesystem":"Filesystem",
    "mcp.presetStdio":"Custom Stdio","mcp.presetHttp":"Custom HTTP",
    "status.title":"System Status","status.refresh":"Refresh","status.loading":"Loading…","status.loadFail":"Load failed: ",
    "status.configFile":"Config File","status.workspace":"Workspace","status.currentModel":"Current Model",
    "status.providers":"LLM Providers","status.configured":"Configured","status.notConfigured":"Not Configured",
    "status.channels":"Channel Status","status.enabled":"Enabled","status.disabled":"Disabled",
    "status.mcpTools":"MCP Tool Services","status.cases":"Feedback Cases",
    "status.mcpConnected":"Connected","status.mcpNotConnected":"Not connected","status.mcpNoTools":"No tools registered",
    "status.mcpTest":"Test Connection","status.mcpReconnect":"Reconnect","status.mcpTesting":"Testing…","status.mcpReconnecting":"Reconnecting…",
    "status.mcpLog":"Diagnostic Log","status.mcpRegisteredTools":"Registered Tools",
    "status.positiveCases":"Positive (👍)","status.negativeCases":"Negative (👎)",
    "status.recentPositive":"Recent Positive","status.recentNegative":"Recent Negative",
    "gw.title":"Gateway Control","gw.stopped":"Gateway Stopped","gw.running":"Gateway Running",
    "gw.stoppedDesc":"Start gateway to connect Telegram, Discord, etc.","gw.runningDesc":"Gateway is processing channel messages",
    "gw.start":"Start Gateway","gw.stop":"Stop Gateway","gw.logs":"Gateway Logs",
    "gw.started":"Gateway started","gw.startFail":"Failed to start","gw.stopFail":"Failed to stop","gw.stoppedMsg":"Gateway stopped",
    "common.onboardOk":"Initialization successful!","common.onboardFail":"Initialization failed",
    "voice.ttsToggle":"Voice alerts","voice.listening":"Listening…","voice.unsupported":"Voice input not supported",
    "voice.ttsOn":"Voice alerts enabled","voice.ttsOff":"Voice alerts disabled",
    "security.mode":"Mode:","security.switched":"Security mode switched to","security.switchFail":"Switch failed",
    "security.modeName.Observer":"Observer","security.modeName.Assistant":"Assistant",
    "security.modeName.Operator":"Operator","security.modeName.Developer":"Developer",
    "security.Observer":"Observer — Auto-create only","security.Assistant":"Assistant — Auto-modify",
    "security.Operator":"Operator — Delete / restore","security.Developer":"Developer — All operations (high risk)",
    "security.opt.Observer":"Observer — Auto-create only","security.opt.Assistant":"Assistant — Auto-modify",
    "security.opt.Operator":"Operator — Delete / restore","security.opt.Developer":"Developer — All operations (high risk)",
    "security.shortDesc.Observer":"Auto-create only","security.shortDesc.Assistant":"Auto-modify",
    "security.shortDesc.Operator":"Delete / restore","security.shortDesc.Developer":"All operations (high risk)",
    "security.devRequired":"Developer mode requires system configuration",
    "security.devEnable":"Enable Developer Mode","security.devDisable":"Disable Developer Mode",
    "security.devExpiry":"Expiry Policy","security.devExpiry.on_app_close":"Expire on app close",
    "security.devExpiry.duration_1h":"Expire after 1 hour","security.devExpiry.duration_24h":"Expire after 24 hours",
    "security.devActive":"Developer mode is active","security.devExpired":"Developer mode expired",
    "security.devRemaining":"Time remaining",
    "settings.auditDesc":"View operation audit trail and undoable action history.",
    "settings.auditOpen":"Open Audit Log",
    "security.devCard.title":"🛡️ Developer — All operations (high risk)",
    "security.devCard.desc":"Developer mode enables all operations including file deletion, command execution, and network exfiltration. Use only in trusted environments with an expiry policy.",
    "security.devCard.btn":"⚙️ Configure Developer Mode",
    "security.devCard.warning":"Developer — All operations (high risk), including file deletion, system commands, data exfiltration. Choose an expiry policy to limit risk.",
    "security.devClose":"Close","security.devUnit.min":"minutes","security.devDisabled":"Developer mode disabled",
    "nav.audit":"Audit","audit.title":"Audit Log","audit.verify":"Verify Chain","audit.export":"Export",
    "audit.recentActions":"Recent Undoable Actions","audit.empty":"No audit entries yet","audit.chainValid":"Audit chain integrity verified",
    "audit.chainInvalid":"Audit chain verification failed","audit.undoSuccess":"Undo successful","audit.undoFail":"Undo failed",
    "audit.noUndo":"No undoable actions",
    "privacy.title":"Privacy & Personalization","privacy.subtitle":"You control the data. I deliver better results.",
    "privacy.dataTitle":"Use these to tailor your experience",
    "privacy.browserHistory":"Browsing history","privacy.browserHint":"Stay closer to what you've been exploring",
    "privacy.chatHistory":"Conversations","privacy.chatHint":"Stay closer to what you're thinking about",
    "privacy.fileHistory":"File changes","privacy.fileHint":"Stay closer to your current work",
    "privacy.watchPaths":"Watch Folders","privacy.watchPathsHelp":"Enter folder paths to monitor, one per line. e.g.: D:\\Projects",
    "privacy.retention":"Retention (days)","privacy.generate":"Generate personalization","privacy.clear":"Clear personalization",
    "privacy.analysisDays":"Analysis window (days)","privacy.analysisDaysHelp":"Analyze last N days when generating persona — no history stored",
    "privacy.localNote":"All data is processed locally by default.",
    "privacy.usageTitle":"Persona Usage Scope",
    "privacy.personaInDigest":"Allow persona-enhanced AI replies","privacy.personaInDigestHint":"Persona is injected into system prompt only — never visible in conversations",
    "privacy.personaUsageNote":"When enabled, AI responses are tailored to your background, but persona data never appears in any conversation message.",
    "privacy.effectTitle":"Current personalization effect",
    "privacy.stablePersona":"Stable Persona","privacy.recentSnapshot":"Recent Interests",
    "privacy.statusOff":"Standard mode — not using history data.",
    "privacy.statusOn":"Personalization enabled — improves over time.",
    "privacy.advanced":"Advanced settings",
    "privacy.generating":"Generating...","privacy.generated":"Personalization generated","privacy.cleared":"Personalization cleared","privacy.saved":"Settings saved",
    "privacy.copied":"Copied","privacy.editSaved":"Saved",
    "nav.reports":"Reports","nav.apps":"Apps",
    "reports.title":"Reports","reports.unread":"Unread","reports.24h":"24h","reports.3d":"3 Days","reports.7d":"7 Days","reports.30d":"30 Days","reports.all":"All",
    "reports.empty":"No reports yet","reports.allRead":"All caught up! Try another time range","reports.viewReport":"View",
    "reports.markAllRead":"Mark all read","reports.delete":"Delete","reports.deleteOk":"Deleted","reports.deleteFail":"Delete failed",
    "nav.stats":"Statistics","stats.todayPrefix":"Today","stats.tokenTitle":"Token Usage","stats.searchTitle":"Search API Calls",
    "stats.rangeTotal":"Total","stats.tokenTip":"Today's LLM token usage","stats.searchTip":"Today's search usage / quota per engine",
    "stats.categoryTitle":"Category Usage","stats.categoryPieTitle":"Usage Breakdown","stats.categoryBarTitle":"Avg. per Task","stats.catChat":"Chat","stats.avgTokens":"Avg Tokens","stats.noData":"No data yet",
    "apps.title":"App Center","apps.search":"Search apps…","apps.back":"Back",
    "apps.sortRecommended":"Recommended","apps.sortFrequency":"Most used","apps.sortCreated":"Newest","apps.sortName":"Name",
    "apps.installed":"Installed","apps.notInstalled":"Not installed","apps.comingSoon":"Coming Soon",
    "apps.install":"Install","apps.uninstall":"Uninstall","apps.configure":"Configure","apps.viewReports":"Reports",
    "apps.enabled":"Enabled","apps.disabled":"Disabled",
    "apps.enable":"Enable","apps.disable":"Disable",
    "apps.installOk":"App installed successfully","apps.uninstallOk":"App uninstalled",
    "apps.installFail":"Install failed","apps.uninstallFail":"Uninstall failed",
    "apps.version":"Version","apps.author":"Author",
    "digest.title":"Daily Briefing","digest.subtitle":"Your personal curator — daily picks tailored to your interests",
    "digest.privacyNote":"🔒 Browsing history is read and analysed locally on your device only — never uploaded to any server.",
    "digest.status":"Status","digest.config":"Settings",
    "digest.browser":"Browser","digest.browserAuto":"Auto detect","digest.browserChrome":"Chrome","digest.browserEdge":"Edge",
    "digest.historyHours":"History range (hours)","digest.scheduleTime":"Daily generation time",
    "digest.pushNotification":"Push notification","digest.pushEmail":"Email push",
    "digest.runNow":"Generate Now","digest.running":"Generating…","digest.saveConfig":"Save Settings",
    "digest.configSaved":"Settings saved","digest.configFail":"Save failed",
    "digest.reports":"Past Briefings","digest.noReports":"No briefings yet",
    "digest.preview":"Interest Preview","digest.previewDesc":"Quick analysis of current browser history interests (AI-powered when available)",
    "digest.previewBtn":"Preview Interests","digest.previewLoading":"Analyzing…",
    "digest.previewMethod":"Method","digest.previewRuleBased":"Rule-based",
    "digest.work":"Work","digest.study":"Study","digest.life":"Life",
    "digest.rawCount":"Raw records","digest.filteredCount":"Valid records","digest.chatCount":"Chats/Msgs","digest.keywordCount":"Interests","digest.searchResults":"Recommendations",
    "digest.viewReport":"View","digest.lastRun":"Last run",
    "digest.generating":"Preparing your briefing…","digest.generateOk":"Your briefing is ready!",
    "digest.generateFail":"Generation failed","digest.noHistory":"No browser history found",
    "digest.latestReport":"Latest Briefing",
    "digest.explore":"Let's Discuss","digest.exploreFail":"Explore failed",
    "email.title":"Email Briefing","email.subtitle":"Connect your mailbox, AI-powered categorised briefing",
    "email.imapConfig":"IMAP Settings","email.host":"Server","email.port":"Port",
    "email.user":"Username","email.password":"Password / App Key","email.ssl":"SSL",
    "email.folder":"Folder","email.hours":"Time Range (hours)","email.maxEmails":"Max Emails",
    "email.scheduleTime":"Daily Generation Time","email.presets":"Quick Fill",
    "email.testConn":"Test Connection","email.testing":"Testing…","email.testOk":"Connected",
    "email.testFail":"Connection Failed","email.runNow":"Generate Now","email.running":"Generating…",
    "email.saveConfig":"Save Settings","email.configSaved":"Settings Saved",
    "email.reports":"Report History","email.noReports":"No reports yet","email.viewReport":"View",
    "custom.title":"Custom App","custom.create":"New Custom App","custom.createFromChat":"Save as App",
    "custom.name":"App Name","custom.icon":"Icon","custom.template":"Task Description",
    "custom.templateHelp":"Use {{variable}} for dynamic parts, e.g.: Search {{keywords}} for latest news",
    "custom.appType":"App Type","custom.type.search":"Web Search","custom.type.content":"Content Generation",
    "custom.safetyNote":"App capabilities are determined by its security mode",
    "custom.safetyModeHint":"Current mode: ",
    "custom.securityMode":"App Security Mode",
    "custom.securityModeInherit":"Inherit global mode",
    "custom.securityModeHint":"Selecting a higher mode grants more capabilities but increases risk",
    "custom.injectProfile":"Inject Personal Profile","custom.injectProfileHelp":"Automatically attach your interests, topics, and project context to the prompt for personalized results",
    "custom.escalation.title":"Security Mode Escalation",
    "custom.escalation.from":"Current global mode",
    "custom.escalation.to":"Requested app mode",
    "custom.escalation.gained":"Additional capabilities gained",
    "custom.escalation.warnings":"Risk warnings",
    "custom.escalation.confirm":"I understand the risks, confirm",
    "custom.escalation.cancel":"Cancel",
    "custom.escalation.noEsc":"{target} does not exceed global {global}, no confirmation needed",
    "custom.escalation.risk.low":"Low","custom.escalation.risk.medium":"Medium",
    "custom.escalation.risk.high":"High","custom.escalation.risk.critical":"Critical",
    "custom.searchEngine":"Search Engine",
    "custom.outputFmt":"Output Format","custom.fmt.report":"HTML Report","custom.fmt.notification":"Notification","custom.fmt.text":"Plain Text",
    "custom.schedule":"Schedule","custom.scheduleTime":"Run Time","custom.scheduleEnabled":"Enable Schedule",
    "custom.schedMode":"Frequency","custom.sched.daily":"Daily","custom.sched.weekly":"Weekly","custom.sched.monthly":"Monthly","custom.sched.interval":"Interval (days)",
    "custom.schedDow":"Weekday","custom.schedDom":"Day of Month","custom.schedInterval":"Interval Days",
    "custom.weekdays":"Mon,Tue,Wed,Thu,Fri,Sat,Sun",
    "custom.catchup":"Smart Catch-up","custom.catchup.none":"No catch-up (skip missed)","custom.catchup.latest":"Catch up latest only (recommended)","custom.catchup.all":"Catch up all missed",
    "custom.catchup.noneHelp":"Skip missed runs, suitable for reminders","custom.catchup.latestHelp":"Will compensate one run next time you open the app","custom.catchup.allHelp":"Suitable for daily reports / monitoring, avoid missing days",
    "custom.catchup.window":"Catch-up Window","custom.catchup.window24":"Past 24 hours","custom.catchup.window168":"Past 7 days",
    "custom.catchup.maxRuns":"Max catch-up runs","custom.catchup.advanced":"Advanced Options",
    "custom.summary":"Summary","custom.summaryEnabled":"Enable Summary","custom.summaryPrompt":"Summary Requirements",
    "custom.summaryPromptHelp":"Describe how to summarize historical data. Leave empty for default.",
    "custom.summaryRun":"Generate Summary","custom.summarySchedule":"Scheduled Summary",
    "custom.summaryFormat":"Output Format","custom.summaryRange":"Analysis Range",
    "custom.summaryFmtHtml":"HTML Report","custom.summaryFmtText":"Plain Text",
    "custom.summaryRangeDays":"days","custom.summaryRangeWeeks":"weeks","custom.summaryRangeMonths":"months",
    "custom.save":"Save App","custom.saving":"Saving…","custom.saved":"App saved",
    "custom.run":"Run Now","custom.running":"Running…","custom.runDone":"Run completed",
    "custom.runFail":"Run failed","custom.edit":"Edit","custom.delete":"Delete",
    "custom.reports":"Reports","custom.summaries":"Summary Reports","custom.noReports":"No reports yet","custom.viewReport":"View",
    "custom.addGroup":"Add Group","custom.removeGroup":"Remove","custom.group":"Group {n}",
    "custom.step1":"Type & Task","custom.step2":"Schedule & Summary","custom.step3":"App Info",
    "custom.next":"Next","custom.prev":"Back","custom.cancel":"Cancel",
    "custom.badge":"Custom",
  },
};

let _lang = "zh";

function detectLang() {
  const stored = localStorage.getItem("nanobot_lang");
  if (stored && stored !== "auto") return stored;
  const nav = (navigator.language || "").toLowerCase();
  return nav.startsWith("zh") ? "zh" : "en";
}

// ── i18n ───────────────────────────────────────────────────────────
// Use t() function provided by i18n.js (loaded in index.html)
// This is a fallback wrapper in case i18n.js not loaded
function t(key) { 
  // If global t() from i18n.js exists, use it
  if (typeof window.t === 'function' && window.t !== t) {
    return window.t(key);
  }
  // Fallback to embedded messages
  return (FALLBACK_I18N[_lang] && FALLBACK_I18N[_lang][key]) || (FALLBACK_I18N.zh && FALLBACK_I18N.zh[key]) || key; 
}

function setLanguage(val) {
  localStorage.setItem("nanobot_lang", val);
  _lang = (val === "auto") ? detectLang() : val;
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = val;
  const radio = document.querySelector(`input[name="lang-radio"][value="${val}"]`);
  if (radio) radio.checked = true;
  applyLanguage();
  fetch("/api/desk/lang", {method:"POST", headers:authHeaders({"Content-Type":"application/json"}), body: JSON.stringify({lang: _lang})}).catch(()=>{});
}

function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return;
    if (el.tagName === "OPTION") {
      el.textContent = t(key);
      return;
    }
    el.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  _refreshSecurityModeLabels();
  renderChatFromHistory();
  renderSessionList();
  const chatInput = document.getElementById("chat-input");
  if (chatInput) chatInput.placeholder = t("chat.placeholder");
}

function _refreshSecurityModeLabels() {
  const sel = document.getElementById("security-mode-select");
  if (sel) {
    sel.querySelectorAll("option[data-i18n]").forEach(opt => {
      opt.textContent = t(opt.dataset.i18n);
    });
    const devOpt = sel.querySelector('option[value="Developer"]');
    if (devOpt) devOpt.textContent = t("security.opt.Developer");
  }
  const hint = document.getElementById("security-mode-hint");
  if (hint && currentSecurityMode) {
    hint.textContent = t(`security.${currentSecurityMode}`) || "";
  }
}

// ── State ─────────────────────────────────────────────────────────────

let currentPage = "chat";
let sessionId = "desktop:0";
let chatBusy = false;
let configCache = null;
let chatMessages = [];

const CHANNEL_NAMES = {
  telegram: "Telegram", discord: "Discord", whatsapp: "WhatsApp",
  feishu: "飞书", mochat: "Mochat", dingtalk: "钉钉",
  email: "Email", slack: "Slack", qq: "QQ",
};

// ── Initialization ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  _lang = detectLang();
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = localStorage.getItem("nanobot_lang") || "auto";
  fetch("/api/desk/lang", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({lang: _lang})}).catch(()=>{});
  setupInput();

  // Intercept all link clicks — open external URLs in system browser
  document.body.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a) return;
    const href = a.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;
    e.preventDefault();
    window.open(href, "_blank");
  });

  const splashMinReady = new Promise(r => setTimeout(r, 3000));

  let _initDone = false;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      await checkSystem(/* delaySplash */ true);
      _initDone = true;
      break;
    } catch (_) {
      await new Promise(r => setTimeout(r, 1000 + attempt * 500));
    }
  }

  await splashMinReady;
  hideSplash();
});

function hideSplash() {
  const splash = document.getElementById("splash");
  const app = document.getElementById("app-root");
  if (splash) splash.classList.add("hidden");
  if (app) app.style.opacity = "1";
}

async function checkSystem(delaySplash) {
  const timeout = (ms) => new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms));
  const splash = delaySplash ? () => {} : hideSplash;
  try {
    const [res] = await Promise.all([
      Promise.race([api("/api/check"), timeout(8000)]),
      window.__libsReady || Promise.resolve(),
    ]);
    if (!res.nanobot_installed) {
      splash();
      applyLanguage();
      showSetup("install");
      return;
    }
    if (!res.config_exists) {
      splash();
      applyLanguage();
      showSetup("onboard");
      return;
    }
    await Promise.race([
      Promise.all([loadSessionList(), loadConfig()]),
      timeout(10000),
    ]);
    await loadLastSessionOrNew();
    switchPage("chat");
    applyLanguage();
    splash();
    startNotificationPoll();
    updateUnreadBadges();
    updateSidebarStats();
    updateTaskPanel();
    _startBadgePoll();
  } catch (e) {
    splash();
    applyLanguage();
    showSetup("install");
  }
}

let _notifTimer = null;
function startNotificationPoll() {
  if (_notifTimer) return;
  _notifTimer = setInterval(pollNotifications, 5000);
}
async function pollNotifications() {
  try {
    const items = await api("/api/notifications");
    if (!items || !items.length) return;
    items.forEach(n => {
      toast(`🔔 ${n.title}\n${n.content}`, n.level === "error" ? "error" : "success", 8000);
    });
  } catch (_) {}
}

function showSetup(stage) {
  document.querySelectorAll(".page").forEach((p) => (p.style.display = "none"));
  document.getElementById("page-setup").style.display = "flex";
  const steps = ["step-install", "step-onboard", "step-apikey"];
  const idx = stage === "install" ? 0 : stage === "onboard" ? 1 : 2;
  steps.forEach((id, i) => {
    const el = document.getElementById(id);
    el.classList.toggle("done", i < idx);
  });
}

async function doOnboard() {
  try {
    const res = await api("/api/onboard", "POST");
    if (res.success) {
      toast(t("common.onboardOk"), "success");
      showSetup("apikey");
    } else {
      toast(res.error || t("common.onboardFail"), "error");
    }
  } catch (e) {
    toast(t("common.onboardFail") + ": " + e.message, "error");
  }
}

// ── Navigation ────────────────────────────────────────────────────────

function switchPage(page) {
  currentPage = page;
  document.querySelectorAll(".page").forEach((p) => (p.style.display = "none"));
  const target = document.getElementById(`page-${page}`);
  if (target) target.style.display = "flex";
  document.querySelectorAll(".nav-item").forEach((n) => {
    const np = n.dataset.page;
    n.classList.toggle("active", np === page || (np === "apps" && page === "app-detail"));
  });
  if (page === "settings") { loadConfig(); _syncGwSettings(); }
  if (page === "stats") { loadTokenChart(); loadSearchChart(); loadCategoryCharts(); }
  if (page === "status") loadStatus();
  if (page === "gateway") loadGatewayStatus();
  if (page === "apps") loadApps();
  if (page === "reports") loadReportsPage();
  if (page === "audit") loadAuditPage();
}

// ── Session list (sidebar) ────────────────────────────────────────────

let sessionListCache = [];

async function loadSessionList() {
  try { sessionListCache = await api("/api/history"); } catch (_) { sessionListCache = []; }
  renderSessionList();
}

function renderSessionList() {
  const container = document.getElementById("session-list");
  if (!sessionListCache.length) {
    container.innerHTML = `<div class="session-empty">${t("chat.noHistory")}</div>`;
    return;
  }
  container.innerHTML = sessionListCache
    .map((s) => {
      const active = s.id === sessionId ? " active" : "";
      const title = escapeHtml(s.title || t("chat.newChat"));
      const sid = escapeAttr(s.id);
      const unread = _unreadSessions.has(s.id) ? `<span class="session-unread-dot"></span>` : "";
      const pending = _pendingResponses[s.id] ? `<span class="session-pending-icon" title="${t("tasks.running")}">⏳</span>` : "";
      return `<div class="session-item${active}" data-sid="${sid}" onclick="switchSession('${sid}')">
        <span class="session-icon">💬</span>
        ${unread}
        <span class="session-title" title="${title}" ondblclick="event.stopPropagation();startRenameSession('${sid}')">${title}</span>
        ${pending}
        <button class="session-edit" onclick="event.stopPropagation();startRenameSession('${sid}')" title="${t("chat.rename")}">✏️</button>
        <button class="session-delete" onclick="event.stopPropagation();deleteSession('${sid}')" title="${t("mcp.delete")}">✕</button>
      </div>`;
    })
    .join("");
}

function startRenameSession(sid) {
  const item = document.querySelector(`.session-item[data-sid="${sid}"]`);
  if (!item) return;
  const titleSpan = item.querySelector(".session-title");
  const s = sessionListCache.find(x => x.id === sid);
  const oldTitle = s ? (s.title || t("chat.newChat")) : titleSpan.textContent;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "session-rename-input";
  input.value = oldTitle;
  input.placeholder = t("chat.renamePlaceholder");

  titleSpan.replaceWith(input);
  input.focus();
  input.select();

  item.querySelector(".session-edit")?.style.setProperty("display", "none");

  const finish = async (save) => {
    if (input._done) return;
    input._done = true;
    const newTitle = input.value.trim();
    if (save && newTitle && newTitle !== oldTitle) {
      try {
        await api(`/api/history/${encodeURIComponent(sid)}/rename`, "POST", { title: newTitle });
        const cached = sessionListCache.find(x => x.id === sid);
        if (cached) cached.title = newTitle;
      } catch (_) {}
    }
    renderSessionList();
  };

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    if (e.key === "Escape") { e.preventDefault(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

async function loadLastSessionOrNew() { await newChat(true); }

async function switchSession(sid, skipPageSwitch = false) {
  sessionId = sid;
  _unreadSessions.delete(sid);
  chatMessages = [];
  try { const res = await api(`/api/history/${encodeURIComponent(sid)}`); chatMessages = res.messages || []; } catch (_) {}
  renderChatFromHistory();

  if (_pendingResponses[sid]) {
    chatBusy = true;
    document.getElementById("send-btn").disabled = true;
    appendThinking();
  } else {
    chatBusy = false;
    document.getElementById("send-btn").disabled = false;
  }

  renderSessionList();
  if (!skipPageSwitch) switchPage("chat");
}

async function deleteSession(sid) {
  try { await api(`/api/history/${encodeURIComponent(sid)}`, "DELETE"); } catch (_) {}
  sessionListCache = sessionListCache.filter((s) => s.id !== sid);
  if (sid === sessionId) {
    if (sessionListCache.length) await switchSession(sessionListCache[0].id);
    else await newChat();
  }
  renderSessionList();
}

// ── Chat ──────────────────────────────────────────────────────────────

function setupInput() {
  const input = document.getElementById("chat-input");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  input.addEventListener("input", autoResize);
}

function autoResize() {
  const el = document.getElementById("chat-input");
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function renderChatFromHistory() {
  const container = document.getElementById("chat-messages");
  if (!chatMessages.length) {
    container.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon">🌀</div>
        <h2>${t("chat.ready")}</h2>
        <p>${t("chat.readyDesc")}</p>
      </div>`;
    return;
  }
  container.innerHTML = "";
  const lastBotIdx = _findLastBotIndex();
  for (let i = 0; i < chatMessages.length; i++) {
    const msg = chatMessages[i];
    const isLast = (i === lastBotIdx);
    appendMessageDOM(msg.role, msg.content, !!msg.markdown, i, msg.feedback || null, isLast, msg.steps || null, msg.audit || null);
  }
}

function _findLastBotIndex() {
  for (let i = chatMessages.length - 1; i >= 0; i--) {
    if (chatMessages[i].role === "bot") return i;
  }
  return -1;
}

function _hidePreviousFeedback() {
  document.querySelectorAll(".message-feedback").forEach(el => el.remove());
}

// Track pending background responses per session
let _pendingResponses = {};
let _unreadSessions = new Set();

async function sendMessage() {
  if (chatBusy) return;
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "auto";
  document.getElementById("send-btn").disabled = true;
  chatBusy = true;

  const msgSessionId = sessionId;

  clearWelcome();
  appendMessageDOM("user", text);
  chatMessages.push({ role: "user", content: text, markdown: false });
  _hidePreviousFeedback();

  await _persistSession(msgSessionId, chatMessages);

  const thinkingId = appendThinking();

  _startBackgroundChat(msgSessionId, text, thinkingId);
}

function _startBackgroundChat(msgSessionId, text, thinkingId) {
  _pendingResponses[msgSessionId] = true;
  const isActive = () => sessionId === msgSessionId;

  let progressBlockId = null;
  let progressSteps = [];

  (async () => {
    let finalContent = null;
    let finalUsage = null;
    let finalAudit = null;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: msgSessionId }),
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "progress") {
              if (isActive()) {
                if (!progressBlockId) { removeElement(thinkingId); progressBlockId = appendProgressBlock(); }
                progressSteps.push(data.content);
                addProgressStep(progressBlockId, data.content);
              } else {
                progressSteps.push(data.content);
              }
            } else if (data.type === "done") {
              finalContent = data.content;
              if (data.usage) finalUsage = data.usage;
              if (data.audit) finalAudit = data.audit;
            } else if (data.type === "error") {
              finalContent = t("chat.error") + data.content;
            }
          } catch (_) {}
        }
      }
    } catch (e) {
      finalContent = t("chat.requestFail") + e.message;
    }

    delete _pendingResponses[msgSessionId];

    const savedMessages = await _loadSessionMessages(msgSessionId);
    const isMd = finalContent ? !finalContent.startsWith(t("chat.error")) : false;
    if (finalContent !== null) {
      savedMessages.push({
        role: "bot", content: finalContent, markdown: isMd, feedback: null,
        steps: progressSteps.length ? progressSteps : undefined,
        audit: finalAudit || undefined,
      });
    }
    await _persistSession(msgSessionId, savedMessages);

    if (isActive()) {
      chatMessages = savedMessages;
      const hasProgressDom = progressBlockId && document.getElementById(progressBlockId);
      const hasThinkingDom = document.querySelector(".thinking-message");
      if (hasProgressDom) {
        _removeAllThinking();
        closeProgressBlock(progressBlockId, progressSteps.length, finalAudit);
        if (finalContent !== null) {
          _injectFinalIntoProgressBlock(progressBlockId, finalContent, chatMessages.length - 1, finalUsage, isMd);
        }
      } else if (hasThinkingDom && finalContent !== null) {
        _removeAllThinking();
        const msgEl = appendMessageDOM("bot", finalContent, isMd, chatMessages.length - 1, null, true);
        if (finalUsage && msgEl) appendUsageBadge(msgEl, finalUsage);
      } else {
        renderChatFromHistory();
      }
      chatBusy = false;
      document.getElementById("send-btn").disabled = false;
      document.getElementById("chat-input").focus();
      renderSessionList();
    } else {
      _unreadSessions.add(msgSessionId);
      renderSessionList();
      if (!_pendingResponses[sessionId]) {
        chatBusy = false;
        document.getElementById("send-btn").disabled = false;
      }
    }
  })();
}

async function _persistSession(sid, messages) {
  if (!messages.length) return;
  const firstUser = messages.find((m) => m.role === "user");
  const title = firstUser ? firstUser.content.slice(0, 50) : t("chat.newChat");
  try { await api(`/api/history/${encodeURIComponent(sid)}`, "POST", { title, messages }); } catch (_) {}
  await loadSessionList();
}

async function _loadSessionMessages(sid) {
  try {
    const res = await api(`/api/history/${encodeURIComponent(sid)}`);
    return res.messages || [];
  } catch (_) { return []; }
}

async function persistCurrentSession() {
  await _persistSession(sessionId, chatMessages);
}

async function newChat(skipPageSwitch = false) {
  try { const res = await api("/api/chat/new", "POST"); if (res.session_id) sessionId = res.session_id; }
  catch (_) { sessionId = "desktop:" + Date.now(); }
  chatMessages = [];
  chatBusy = false;
  document.getElementById("send-btn").disabled = false;
  renderChatFromHistory();
  renderSessionList();
  if (!skipPageSwitch) switchPage("chat");
}

function clearWelcome() { const w = document.querySelector(".welcome-message"); if (w) w.remove(); }

function appendMessageDOM(type, content, renderMd = false, msgIndex = -1, existingFeedback = null, isLast = false, steps = null, audit = null) {
  const container = document.getElementById("chat-messages");
  const id = "msg-" + Date.now() + Math.random().toString(36).slice(2, 6);
  const isUser = type.includes("user");
  const isProgress = type.includes("progress");
  const isBotFinal = !isUser && !isProgress;
  const className = isUser ? "message user" : isProgress ? "message bot progress" : "message bot";

  const div = document.createElement("div");
  div.className = className;
  div.id = id;

  const avatar = isUser ? "👤" : "🌀";
  const sender = isUser ? t("chat.you") : "nanobot";

  let rendered;
  if (!isUser && typeof content === "string" && content.includes("[BLOCKED]")) {
    const lines = content.split("\n").filter(Boolean);
    rendered = `<div class="risk-card risk-card-blocked">
      <div class="risk-card-header"><span class="risk-icon">🛑</span> 操作已拦截</div>
      <div class="risk-card-body">${escapeHtml(lines.slice(0).join("\n"))}</div>
    </div>`;
  } else if (!isUser && typeof content === "string" && content.includes("[NEEDS CONFIRM]")) {
    const lines = content.split("\n").filter(Boolean);
    rendered = `<div class="risk-card risk-card-confirm">
      <div class="risk-card-header"><span class="risk-icon">⚠️</span> 需要确认</div>
      <div class="risk-card-body">${escapeHtml(lines.slice(0).join("\n"))}</div>
      <div class="risk-card-hint">请在弹出的确认窗口中批准或拒绝此操作。</div>
    </div>`;
  } else {
    rendered = renderMd ? renderMarkdown(content) : escapeHtml(content);
  }

  let stepsHtml = "";
  if (steps && steps.length && isBotFinal) {
    stepsHtml = renderProgressDetails(steps, false, audit);
  }

  let feedbackHtml = "";
  if (isBotFinal && msgIndex >= 0 && isLast) {
    const likeClass = existingFeedback === "like" ? " selected-like" : existingFeedback === "dislike" ? " dimmed" : "";
    const dislikeClass = existingFeedback === "dislike" ? " selected-dislike" : existingFeedback === "like" ? " dimmed" : "";
    const commentText = existingFeedback ? `<span class="feedback-comment">${t("chat.rated")}</span>` : "";
    feedbackHtml = `<div class="message-feedback" data-msgindex="${msgIndex}">
      <button class="feedback-btn${likeClass}" data-rating="like" onclick="handleFeedback(this)">👍</button>
      <button class="feedback-btn${dislikeClass}" data-rating="dislike" onclick="handleFeedback(this)">👎</button>
      <button class="feedback-btn regenerate-btn" onclick="regenerateMessage(${msgIndex})" title="${t("chat.regenerate")}">🔄</button>
      <button class="feedback-btn save-app-btn" onclick="saveAsCustomApp(${msgIndex})" title="${t("custom.createFromChat")}">💾</button>
      ${commentText}
    </div>`;
  }

  div.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-sender">${sender}</div>
      ${stepsHtml}
      <div class="message-content">${rendered}</div>
      ${feedbackHtml}
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  if (renderMd) highlightCode(div);
  return id;
}

function appendUsageBadge(msgElId, usage) {
  const msgEl = document.getElementById(msgElId);
  if (!msgEl) return;
  const body = msgEl.querySelector(".message-body");
  if (!body) return;
  const inp = (usage.input || 0).toLocaleString();
  const out = (usage.output || 0).toLocaleString();
  const badge = document.createElement("div");
  badge.className = "message-usage";
  let html = `<span>tokens: ${inp} in / ${out} out</span>`;
  if (usage.search) html += `<span class="message-usage-sep">|</span><span>search: ${usage.search}</span>`;
  badge.innerHTML = html;
  body.appendChild(badge);
}

async function handleFeedback(btn) {
  if (btn.classList.contains("selected-like") || btn.classList.contains("selected-dislike") || btn.classList.contains("dimmed")) return;
  const rating = btn.dataset.rating;
  const feedbackDiv = btn.closest(".message-feedback");
  const msgIndex = parseInt(feedbackDiv.dataset.msgindex);

  let comment = "";
  if (rating === "dislike") comment = prompt(t("chat.askDislike")) || "";

  const botMsg = chatMessages[msgIndex];
  if (!botMsg) return;
  let promptText = "";
  for (let i = msgIndex - 1; i >= 0; i--) { if (chatMessages[i].role === "user") { promptText = chatMessages[i].content; break; } }

  try { await api("/api/feedback", "POST", { rating, prompt: promptText, answer: botMsg.content, comment, session_id: sessionId }); } catch (_) {}
  botMsg.feedback = rating;
  persistCurrentSession();

  const likeBtn = feedbackDiv.querySelector('[data-rating="like"]');
  const dislikeBtn = feedbackDiv.querySelector('[data-rating="dislike"]');
  if (rating === "like") { likeBtn.classList.add("selected-like"); dislikeBtn.classList.add("dimmed"); }
  else { dislikeBtn.classList.add("selected-dislike"); likeBtn.classList.add("dimmed"); }

  let commentEl = feedbackDiv.querySelector(".feedback-comment");
  if (!commentEl) { commentEl = document.createElement("span"); commentEl.className = "feedback-comment"; feedbackDiv.appendChild(commentEl); }
  commentEl.textContent = rating === "like" ? t("chat.thankFeedback") : t("chat.willImprove");
}

async function regenerateMessage(botMsgIndex) {
  if (chatBusy) return;

  let userText = "";
  for (let i = botMsgIndex - 1; i >= 0; i--) {
    if (chatMessages[i].role === "user") { userText = chatMessages[i].content; break; }
  }
  if (!userText) return;

  chatMessages.splice(botMsgIndex, 1);
  renderChatFromHistory();

  chatBusy = true;
  document.getElementById("send-btn").disabled = true;
  _hidePreviousFeedback();

  await _persistSession(sessionId, chatMessages);

  const thinkingId = appendThinking();
  _startBackgroundChat(sessionId, userText, thinkingId);
}

function appendThinking() {
  const container = document.getElementById("chat-messages");
  const id = "thinking-" + Date.now();
  const div = document.createElement("div");
  div.className = "message bot thinking-message"; div.id = id;
  div.innerHTML = `<div class="message-avatar">🌀</div><div class="message-body"><div class="message-sender">nanobot</div><div class="message-content"><div class="thinking-dots"><span></span><span></span><span></span></div></div></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function _removeAllThinking() {
  document.querySelectorAll(".thinking-message").forEach(el => el.remove());
}

function appendProgressBlock() {
  const container = document.getElementById("chat-messages");
  const id = "exec-" + Date.now() + Math.random().toString(36).slice(2, 6);
  const div = document.createElement("div");
  div.className = "message bot exec-progress-wrap";
  div.id = id;
  div.innerHTML = `<div class="message-avatar">🌀</div>
    <div class="message-body"><div class="message-sender">nanobot</div>
      <details class="exec-details" open>
        <summary class="exec-summary"><span class="exec-summary-icon">⏳</span> <span class="exec-summary-text">${t("chat.executing") || "执行中…"}</span></summary>
        <div class="exec-steps"></div>
      </details>
    </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function addProgressStep(blockId, content) {
  const el = document.getElementById(blockId);
  if (!el) return;
  const steps = el.querySelector(".exec-steps");
  if (!steps) return;
  const step = document.createElement("div");
  step.className = "exec-step";
  step.textContent = content;
  steps.appendChild(step);
  const container = document.getElementById("chat-messages");
  if (container) container.scrollTop = container.scrollHeight;
}

function closeProgressBlock(blockId, stepCount, audit) {
  const el = document.getElementById(blockId);
  if (!el) return;
  const details = el.querySelector(".exec-details");
  if (details) details.removeAttribute("open");
  const icon = el.querySelector(".exec-summary-icon");
  if (icon) icon.textContent = "✅";
  const txt = el.querySelector(".exec-summary-text");
  let label = (t("chat.execDone") || "执行完成") + ` (${stepCount} ${t("chat.steps") || "步"})`;
  if (audit && audit.fingerprint) label += ` · fp:${audit.fingerprint}`;
  if (txt) txt.textContent = label;
}

function renderProgressDetails(steps, open, audit) {
  if (!steps || !steps.length) return "";
  const icon = open ? "⏳" : "✅";
  let label = open ? (t("chat.executing") || "执行中…") : (t("chat.execDone") || "执行完成") + ` (${steps.length} ${t("chat.steps") || "步"})`;
  if (!open && audit && audit.fingerprint) label += ` · fp:${audit.fingerprint}`;
  return `<details class="exec-details"${open ? " open" : ""}>
    <summary class="exec-summary"><span class="exec-summary-icon">${icon}</span> <span class="exec-summary-text">${label}</span></summary>
    <div class="exec-steps">${steps.map(s => `<div class="exec-step">${escapeHtml(s)}</div>`).join("")}</div>
  </details>`;
}

function _injectFinalIntoProgressBlock(blockId, content, msgIndex, usage, asMd = true) {
  const el = document.getElementById(blockId);
  if (!el) return;
  const body = el.querySelector(".message-body");
  if (!body) return;

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.innerHTML = asMd ? renderMarkdown(content) : escapeHtml(content);
  body.appendChild(contentDiv);
  if (asMd) highlightCode(contentDiv);

  if (msgIndex >= 0) {
    const fb = document.createElement("div");
    fb.className = "message-feedback";
    fb.dataset.msgindex = msgIndex;
    fb.innerHTML = `
      <button class="feedback-btn" data-rating="like" onclick="handleFeedback(this)">👍</button>
      <button class="feedback-btn" data-rating="dislike" onclick="handleFeedback(this)">👎</button>
      <button class="feedback-btn regenerate-btn" onclick="regenerateMessage(${msgIndex})" title="${t("chat.regenerate")}">🔄</button>
      <button class="feedback-btn save-app-btn" onclick="saveAsCustomApp(${msgIndex})" title="${t("custom.createFromChat")}">💾</button>`;
    body.appendChild(fb);
  }

  if (usage) {
    const inp = (usage.input || 0).toLocaleString();
    const out = (usage.output || 0).toLocaleString();
    const badge = document.createElement("div");
    badge.className = "message-usage";
    let html = `<span>tokens: ${inp} in / ${out} out</span>`;
    if (usage.search) html += `<span class="message-usage-sep">|</span><span>search: ${usage.search}</span>`;
    badge.innerHTML = html;
    body.appendChild(badge);
  }

  const container = document.getElementById("chat-messages");
  if (container) container.scrollTop = container.scrollHeight;
}

function updateMessageContent(id, content) {
  const el = document.getElementById(id);
  if (!el) return;
  const c = el.querySelector(".message-content");
  if (c) c.textContent = content;
}

function removeElement(id) { const el = document.getElementById(id); if (el) el.remove(); }

function renderMarkdown(text) {
  if (!text) return "";
  if (typeof marked !== "undefined") {
    marked.setOptions({ breaks: true, gfm: true, highlight: function (code, lang) {
      if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
      return code;
    }});
    return marked.parse(text);
  }
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function highlightCode(container) {
  if (typeof hljs === "undefined") return;
  container.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
}

function escapeHtml(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }
function escapeAttr(s) { return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;"); }

// ── Config / Settings ─────────────────────────────────────────────────

const PROVIDER_FIELDS = [
  { id: "cfg-openrouter-key", path: ["providers", "openrouter", "apiKey"] },
  { id: "cfg-anthropic-key", path: ["providers", "anthropic", "apiKey"] },
  { id: "cfg-openai-key", path: ["providers", "openai", "apiKey"] },
  { id: "cfg-deepseek-key", path: ["providers", "deepseek", "apiKey"] },
  { id: "cfg-gemini-key", path: ["providers", "gemini", "apiKey"] },
  { id: "cfg-groq-key", path: ["providers", "groq", "apiKey"] },
  { id: "cfg-moonshot-key", path: ["providers", "moonshot", "apiKey"] },
  { id: "cfg-zhipu-key", path: ["providers", "zhipu", "apiKey"] },
  { id: "cfg-dashscope-key", path: ["providers", "dashscope", "apiKey"] },
  { id: "cfg-siliconflow-key", path: ["providers", "siliconflow", "apiKey"] },
  { id: "cfg-minimax-key", path: ["providers", "minimax", "apiKey"] },
  { id: "cfg-aihubmix-key", path: ["providers", "aihubmix", "apiKey"] },
];

async function loadConfig() {
  try {
    const data = await api("/api/config");
    if (data.error) { toast(data.error, "error"); return; }
    configCache = data;
    fillConfigForm(data);
  } catch (e) { toast(t("settings.loadFail"), "error"); }
}

function fillConfigForm(cfg) {
  const get = (obj, path) => path.reduce((o, k) => (o && o[k] !== undefined ? o[k] : ""), obj);
  document.getElementById("cfg-model").value = get(cfg, ["agents", "defaults", "model"]) || "";
  document.getElementById("cfg-temperature").value = get(cfg, ["agents", "defaults", "temperature"]) || 0.7;
  document.getElementById("temp-value").textContent = document.getElementById("cfg-temperature").value;
  document.getElementById("cfg-max-tokens").value = get(cfg, ["agents", "defaults", "maxTokens"]) || "";
  document.getElementById("cfg-max-iterations").value = get(cfg, ["agents", "defaults", "maxToolIterations"]) || "";
  document.getElementById("cfg-memory-window").value = get(cfg, ["agents", "defaults", "memoryWindow"]) || "";
  PROVIDER_FIELDS.forEach(({ id, path }) => { document.getElementById(id).value = get(cfg, path) || ""; });
  document.getElementById("cfg-baidu-key").value = get(cfg, ["tools", "web", "search", "baiduApiKey"]) || "";
  document.getElementById("cfg-brave-key").value = get(cfg, ["tools", "web", "search", "apiKey"]) || "";
  document.getElementById("cfg-quota-only").checked = get(cfg, ["tools", "web", "search", "quotaOnly"]) !== false;
  document.getElementById("cfg-exec-timeout").value = get(cfg, ["tools", "exec", "timeout"]) || "";
  document.getElementById("cfg-restrict-workspace").checked = !!get(cfg, ["tools", "restrictToWorkspace"]);
  refreshSearchUsage();

  const grid = document.getElementById("channels-grid");
  grid.innerHTML = "";
  Object.keys(CHANNEL_NAMES).forEach((name) => {
    const enabled = get(cfg, ["channels", name, "enabled"]) || false;
    const div = document.createElement("div");
    div.className = "channel-item";
    div.innerHTML = `<span>${CHANNEL_NAMES[name]}</span><label class="toggle"><input type="checkbox" data-channel="${name}" ${enabled ? "checked" : ""} /><span class="toggle-slider"></span></label>`;
    grid.appendChild(div);
  });

  renderMcpServers(cfg);

  document.getElementById("cfg-json-raw").value = JSON.stringify(cfg, null, 2);
}

// ── Search API Usage ────────────────────────────────────────────────────

function _renderUsageBar(barId, used, limit) {
  const bar = document.getElementById(barId);
  if (!bar) return;
  const pct = limit > 0 ? Math.min(used / limit * 100, 100) : 0;
  const cls = pct >= 100 ? "danger" : pct >= 80 ? "warn" : "";
  const label = pct >= 100
    ? `⚠️ ${t("settings.quotaExhausted")} (${used}/${limit})`
    : `${t("settings.usageToday")}: ${used} / ${limit}`;
  bar.innerHTML = `<span>${label}</span><div class="usage-meter"><div class="usage-meter-fill ${cls}" style="width:${pct}%"></div></div>`;
}

async function refreshSearchUsage() {
  try {
    const data = await api("/api/search/usage");
    if (data && data.engines) {
      const b = data.engines.baidu;
      const v = data.engines.brave;
      if (b) _renderUsageBar("baidu-usage-bar", b.used, b.limit);
      if (v) _renderUsageBar("brave-usage-bar", v.used, v.limit);
    }
  } catch (_) {}
}

// ── MCP Servers ────────────────────────────────────────────────────────

function getMcpPresets() {
  return [
    { label: t("mcp.presetPlaywright"), name: "playwright", type: "stdio", command: "npx", args: ["@playwright/mcp@latest"] },
    { label: t("mcp.presetFilesystem"), name: "filesystem", type: "stdio", command: "npx", args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"] },
    { label: t("mcp.presetStdio"), name: "", type: "stdio", command: "", args: [] },
    { label: t("mcp.presetHttp"), name: "", type: "http", url: "", headers: {} },
  ];
}

function renderMcpServers(cfg) {
  const servers = (cfg && cfg.tools && cfg.tools.mcpServers) || {};
  const container = document.getElementById("mcp-server-list");
  if (!Object.keys(servers).length) {
    container.innerHTML = `<div class="mcp-empty">${t("mcp.empty")}</div>`;
    return;
  }
  container.innerHTML = "";
  Object.entries(servers).forEach(([name, conf]) => container.appendChild(buildMcpServerCard(name, conf)));
}

function buildMcpServerCard(name, conf) {
  const isHttp = !!conf.url;
  const type = isHttp ? "http" : "stdio";
  const div = document.createElement("div");
  div.className = "mcp-server-item";
  div.dataset.mcpName = name;

  let bodyHtml = "";
  if (isHttp) {
    bodyHtml = `<div class="mcp-field-row"><label>URL</label><input type="text" class="mcp-url" value="${escapeAttr(conf.url || "")}" placeholder="https://example.com/mcp/" /></div>
      <div class="mcp-field-row"><label>Headers</label><textarea class="mcp-args-area mcp-headers" rows="2" placeholder='{"Authorization": "Bearer xxx"}'>${escapeHtml(JSON.stringify(conf.headers || {}, null, 2))}</textarea></div>`;
  } else {
    bodyHtml = `<div class="mcp-field-row"><label>Command</label><input type="text" class="mcp-command" value="${escapeAttr(conf.command || "")}" placeholder="npx / uvx / python" /></div>
      <div class="mcp-field-row"><label>Args</label><textarea class="mcp-args-area mcp-args" rows="1" placeholder='${escapeAttr(t("mcp.argsPlaceholder"))}'>${Array.isArray(conf.args) ? conf.args.join("\n") : ""}</textarea></div>
      <div class="mcp-field-help">${t("mcp.argsHelp")}</div>`;
  }

  div.innerHTML = `<div class="mcp-server-header">
      <input type="text" class="mcp-name-input" value="${escapeAttr(name)}" placeholder="${escapeAttr(t("mcp.serverName"))}" />
      <span class="mcp-type-badge ${type}">${type}</span>
      <button class="mcp-delete-btn" onclick="deleteMcpServer(this)">${t("mcp.delete")}</button>
    </div><div class="mcp-server-body">${bodyHtml}</div>`;
  return div;
}

function addMcpServer(presetIdx) {
  if (presetIdx === undefined) { showMcpPresetPicker(); return; }
  const presets = getMcpPresets();
  const preset = presets[presetIdx];
  const container = document.getElementById("mcp-server-list");
  const emptyEl = container.querySelector(".mcp-empty");
  if (emptyEl) emptyEl.remove();

  const name = preset.name || "mcp-" + Date.now().toString(36);
  const conf = preset.type === "http"
    ? { url: preset.url || "", headers: preset.headers || {} }
    : { command: preset.command || "", args: preset.args || [] };

  const card = buildMcpServerCard(name, conf);
  container.appendChild(card);
  card.querySelector(".mcp-name-input").focus();
  card.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showMcpPresetPicker() {
  const existing = document.getElementById("mcp-preset-picker");
  if (existing) { existing.remove(); return; }

  const picker = document.createElement("div");
  picker.id = "mcp-preset-picker";
  picker.style.cssText = "position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.5);";
  picker.onclick = (e) => { if (e.target === picker) picker.remove(); };

  const presets = getMcpPresets();
  let items = presets.map((p, i) =>
    `<div class="mcp-preset-option" onclick="document.getElementById('mcp-preset-picker').remove();addMcpServer(${i})">
      <span class="mcp-type-badge ${p.type}" style="margin-right:8px;">${p.type}</span>
      <strong>${escapeHtml(p.label)}</strong>
      ${p.name ? '<span style="margin-left:auto;font-size:12px;color:var(--text-dim)">' + escapeHtml(p.command || p.url || "") + "</span>" : ""}
    </div>`
  ).join("");

  picker.innerHTML = `<div style="background:var(--bg-mantle);border:1px solid var(--bg-surface0);border-radius:var(--radius-lg);padding:24px;min-width:400px;max-width:500px;">
    <h3 style="margin-bottom:16px;font-size:16px;">${t("mcp.pickTitle")}</h3>
    <div style="display:flex;flex-direction:column;gap:8px;">${items}</div>
    <div style="text-align:right;margin-top:16px;"><button class="btn btn-sm" onclick="this.closest('#mcp-preset-picker').remove()">${t("mcp.cancel")}</button></div>
  </div>`;
  document.body.appendChild(picker);
}

function deleteMcpServer(btn) {
  btn.closest(".mcp-server-item").remove();
  const container = document.getElementById("mcp-server-list");
  if (!container.children.length) container.innerHTML = `<div class="mcp-empty">${t("mcp.empty")}</div>`;
}

function collectMcpServers() {
  const servers = {};
  document.querySelectorAll(".mcp-server-item").forEach((item) => {
    const name = item.querySelector(".mcp-name-input").value.trim();
    if (!name) return;
    const urlInput = item.querySelector(".mcp-url");
    if (urlInput) {
      const conf = { url: urlInput.value.trim() };
      const headersArea = item.querySelector(".mcp-headers");
      if (headersArea) { try { conf.headers = JSON.parse(headersArea.value); } catch (_) { conf.headers = {}; } }
      servers[name] = conf;
    } else {
      const command = (item.querySelector(".mcp-command")?.value || "").trim();
      const argsText = (item.querySelector(".mcp-args")?.value || "").trim();
      let args = [];
      if (argsText) {
        if (argsText.startsWith("[")) { try { args = JSON.parse(argsText); } catch (_) { args = argsText.split("\n").filter(Boolean); } }
        else args = argsText.split("\n").filter(Boolean);
      }
      servers[name] = { command, args };
    }
  });
  return servers;
}

function collectConfigForm() {
  const cfg = configCache ? JSON.parse(JSON.stringify(configCache)) : {};
  const set = (obj, path, val) => {
    for (let i = 0; i < path.length - 1; i++) { if (!obj[path[i]]) obj[path[i]] = {}; obj = obj[path[i]]; }
    obj[path[path.length - 1]] = val;
  };
  const del = (obj, path) => {
    for (let i = 0; i < path.length - 1; i++) { if (!obj[path[i]]) return; obj = obj[path[i]]; }
    delete obj[path[path.length - 1]];
  };
  const setOrDel = (path, val) => { if (val) set(cfg, path, val); else del(cfg, path); };
  set(cfg, ["agents", "defaults", "model"], document.getElementById("cfg-model").value);
  set(cfg, ["agents", "defaults", "temperature"], parseFloat(document.getElementById("cfg-temperature").value) || 0.7);
  const maxTokens = parseInt(document.getElementById("cfg-max-tokens").value);
  if (maxTokens) set(cfg, ["agents", "defaults", "maxTokens"], maxTokens); else del(cfg, ["agents", "defaults", "maxTokens"]);
  const maxIter = parseInt(document.getElementById("cfg-max-iterations").value);
  if (maxIter) set(cfg, ["agents", "defaults", "maxToolIterations"], maxIter); else del(cfg, ["agents", "defaults", "maxToolIterations"]);
  const memWin = parseInt(document.getElementById("cfg-memory-window").value);
  if (memWin) set(cfg, ["agents", "defaults", "memoryWindow"], memWin); else del(cfg, ["agents", "defaults", "memoryWindow"]);
  PROVIDER_FIELDS.forEach(({ id, path }) => { setOrDel(path, document.getElementById(id).value); });
  setOrDel(["tools", "web", "search", "baiduApiKey"], document.getElementById("cfg-baidu-key").value);
  setOrDel(["tools", "web", "search", "apiKey"], document.getElementById("cfg-brave-key").value);
  set(cfg, ["tools", "web", "search", "quotaOnly"], document.getElementById("cfg-quota-only").checked);
  const execTimeout = parseInt(document.getElementById("cfg-exec-timeout").value);
  if (execTimeout) set(cfg, ["tools", "exec", "timeout"], execTimeout); else del(cfg, ["tools", "exec", "timeout"]);
  set(cfg, ["tools", "restrictToWorkspace"], document.getElementById("cfg-restrict-workspace").checked);
  document.querySelectorAll("[data-channel]").forEach((input) => { set(cfg, ["channels", input.dataset.channel, "enabled"], input.checked); });
  if (!cfg.tools) cfg.tools = {};
  cfg.tools.mcpServers = collectMcpServers();

  return cfg;
}

async function saveConfig() {
  const cfg = collectConfigForm();
  try {
    const res = await api("/api/config", "POST", cfg);
    if (res.success) {
      configCache = cfg;
      document.getElementById("cfg-json-raw").value = JSON.stringify(cfg, null, 2);
      toast(t("settings.saved"), "success");
    } else { toast(res.error || t("settings.saveFail"), "error"); }
  } catch (e) { toast(t("settings.saveFail") + ": " + e.message, "error"); }
}

function toggleJsonEditor() {
  const wrap = document.getElementById("json-editor-wrap");
  wrap.style.display = wrap.style.display === "none" ? "block" : "none";
}

function applyRawJson() {
  try {
    const data = JSON.parse(document.getElementById("cfg-json-raw").value);
    configCache = data;
    fillConfigForm(data);
    toast(t("settings.jsonApplied"), "info");
  } catch (e) { toast(t("settings.jsonError") + e.message, "error"); }
}

// ── Stats charts ──────────────────────────────────────────────────────

let _tokenChartDays = 7;
let _searchChartDays = 7;

function _fmtNum(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }

function _renderBarChart(container, items, valueKey, unit) {
  const max = Math.max(...items.map(d => d[valueKey]), 1);
  container.innerHTML = items.map(d => {
    const v = d[valueKey];
    const pct = Math.max((v / max) * 100, v > 0 ? 2 : 0);
    const label = d.date.slice(5);
    return `<div class="token-bar-col">
      <span class="token-bar-tooltip">${d.date}: ${_fmtNum(v)} ${unit}</span>
      <div class="token-bar" style="height:${pct}%"></div>
      <span class="token-bar-label">${label}</span>
    </div>`;
  }).join("");
}

async function loadTokenChart(days) {
  _tokenChartDays = days || _tokenChartDays;
  document.querySelectorAll("#token-chart-tabs .token-chart-tab").forEach(btn => {
    btn.classList.toggle("active", Number(btn.dataset.days) === _tokenChartDays);
  });
  const container = document.getElementById("token-chart-container");
  const totalEl = document.getElementById("token-chart-total");
  if (!container) return;
  try {
    const data = await api(`/api/token/history?days=${_tokenChartDays}`);
    const history = data.history || [];
    const totalIn = history.reduce((s, d) => s + (d.input || 0), 0);
    const totalOut = history.reduce((s, d) => s + (d.output || 0), 0);
    if (totalEl) totalEl.textContent = `↓${_fmtNum(totalIn)}  ↑${_fmtNum(totalOut)}  ${t("stats.rangeTotal")} ${_fmtNum(totalIn + totalOut)}`;
    const max = Math.max(...history.map(d => (d.input || 0) + (d.output || 0)), 1);
    container.innerHTML = history.map(d => {
      const inp = d.input || 0, out = d.output || 0, total = inp + out;
      const pctIn = Math.max((inp / max) * 100, inp > 0 ? 1 : 0);
      const pctOut = Math.max((out / max) * 100, out > 0 ? 1 : 0);
      const label = d.date.slice(5);
      return `<div class="token-bar-col">
        <span class="token-bar-tooltip">${d.date}: ↓${_fmtNum(inp)} ↑${_fmtNum(out)}</span>
        <div class="token-bar token-bar-out" style="height:${pctOut}%"></div>
        <div class="token-bar token-bar-in" style="height:${pctIn}%"></div>
        <span class="token-bar-label">${label}</span>
      </div>`;
    }).join("");
  } catch (_) {
    container.innerHTML = `<span style="color:var(--text-dim);font-size:12px">—</span>`;
  }
}

async function loadSearchChart(days) {
  _searchChartDays = days || _searchChartDays;
  document.querySelectorAll("#search-chart-tabs .token-chart-tab").forEach(btn => {
    btn.classList.toggle("active", Number(btn.dataset.days) === _searchChartDays);
  });
  const container = document.getElementById("search-chart-container");
  const totalEl = document.getElementById("search-chart-total");
  if (!container) return;
  try {
    const data = await api(`/api/search/history?days=${_searchChartDays}`);
    const history = data.history || [];
    const total = data.total || 0;
    if (totalEl) totalEl.textContent = `${t("stats.rangeTotal")} ${_fmtNum(total)} 次`;
    _renderBarChart(container, history, "calls", "次");
  } catch (_) {
    container.innerHTML = `<span style="color:var(--text-dim);font-size:12px">—</span>`;
  }
}

// ── Category charts (Chart.js) ────────────────────────────────────────

let _categoryPieChart = null;
let _categoryBarChart = null;
let _catDays = 7;

const _CHART_COLORS = [
  '#89b4fa', '#a6e3a1', '#f9e2af', '#f38ba8', '#cba6f7',
  '#fab387', '#94e2d5', '#74c7ec', '#f5c2e7', '#b4befe',
];

function _catLabel(key) {
  if (key === 'chat') return t('stats.catChat');
  if (key.startsWith('app_')) return key.slice(4);
  return key;
}

function _emptyCanvas(canvas) {
  const ctx2d = canvas.getContext('2d');
  ctx2d.clearRect(0, 0, canvas.width, canvas.height);
  ctx2d.fillStyle = '#6c7086';
  ctx2d.font = '13px sans-serif';
  ctx2d.textAlign = 'center';
  ctx2d.fillText(t('stats.noData') || '暂无数据', canvas.width / 2, canvas.height / 2);
}

async function loadCategoryCharts(days) {
  _catDays = days || _catDays;
  document.querySelectorAll('#category-chart-tabs .token-chart-tab').forEach(btn => {
    btn.classList.toggle('active', Number(btn.dataset.days) === _catDays);
  });
  const pieCanvas = document.getElementById('category-pie-chart');
  const barCanvas = document.getElementById('category-bar-chart');
  if (!pieCanvas && !barCanvas) return;
  try {
    const data = await api(`/api/usage/categories?days=${_catDays}`);
    const cats = data.categories || {};
    const labels = [], values = [], avgValues = [], colors = [];
    let ci = 0;
    for (const [k, v] of Object.entries(cats)) {
      labels.push(_catLabel(k));
      const total = (v.input || 0) + (v.output || 0);
      values.push(total);
      avgValues.push(Math.round(total / (v.count || 1)));
      colors.push(_CHART_COLORS[ci % _CHART_COLORS.length]);
      ci++;
    }
    const isDark = document.documentElement.classList.contains('dark') ||
                   getComputedStyle(document.body).getPropertyValue('--bg-base').trim() === '#1e1e2e';
    if (_categoryPieChart) _categoryPieChart.destroy();
    _categoryPieChart = null;
    if (pieCanvas) {
      if (!labels.length) { _emptyCanvas(pieCanvas); }
      else {
        _categoryPieChart = new Chart(pieCanvas, {
          type: 'doughnut',
          data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { color: isDark ? '#cdd6f4' : '#333', font: { size: 11 }, boxWidth: 12 } },
              tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed.toLocaleString()} tokens` } },
            },
          },
        });
      }
    }
    if (_categoryBarChart) _categoryBarChart.destroy();
    _categoryBarChart = null;
    if (barCanvas) {
      if (!labels.length) { _emptyCanvas(barCanvas); }
      else {
        _categoryBarChart = new Chart(barCanvas, {
          type: 'bar',
          data: { labels, datasets: [{ label: t('stats.avgTokens'), data: avgValues, backgroundColor: colors, borderRadius: 4 }] },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${t('stats.avgTokens')}: ${ctx.parsed.y.toLocaleString()}` } } },
            scales: {
              x: { ticks: { color: isDark ? '#a6adc8' : '#666', font: { size: 11 } }, grid: { display: false } },
              y: { ticks: { color: isDark ? '#a6adc8' : '#666', font: { size: 11 } }, grid: { color: isDark ? 'rgba(69,71,90,0.4)' : 'rgba(0,0,0,0.1)' } },
            },
          },
        });
      }
    }
  } catch (e) { console.warn('loadCategoryCharts error:', e); }
}

// ── Gateway settings sync ─────────────────────────────────────────────

async function _syncGwSettings() {
  try {
    const s = await api("/api/gateway/status");
    const running = s && s.running;
    const ind = document.getElementById("gw-settings-indicator");
    const txt = document.getElementById("gw-settings-status");
    const startBtn = document.getElementById("gw-settings-start");
    const stopBtn = document.getElementById("gw-settings-stop");
    if (ind) ind.className = `gateway-indicator ${running ? "on" : "off"}`;
    if (txt) txt.textContent = running ? t("gw.running") : t("gw.stopped");
    if (startBtn) startBtn.style.display = running ? "none" : "";
    if (stopBtn) stopBtn.style.display = running ? "" : "none";
  } catch (_) {}
}

// ── Status ────────────────────────────────────────────────────────────

async function loadStatus() {
  const grid = document.getElementById("status-grid");
  grid.innerHTML = `<div class="status-card"><div class="status-label">${t("status.loading")}</div></div>`;

  try {
    const data = await api("/api/status");
    if (data.error) { grid.innerHTML = `<div class="status-card"><div class="status-value err">${data.error}</div></div>`; return; }

    let html = "";
    html += statusCard(t("status.configFile"), data.config_path, data.config_exists ? "ok" : "err");
    html += statusCard(t("status.workspace"), data.workspace, data.workspace_exists ? "ok" : "warn");
    html += statusCard(t("status.currentModel"), data.model, "ok");

    let provHtml = '<div class="provider-list">';
    (data.providers || []).forEach((p) => {
      const badge = p.configured
        ? `<span class="badge badge-ok">${t("status.configured")}</span>`
        : `<span class="badge badge-off">${t("status.notConfigured")}</span>`;
      provHtml += `<div class="provider-row"><span>${p.label || p.name}</span>${badge}</div>`;
    });
    provHtml += "</div>";
    html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.providers")}</h3>${provHtml}</div>`;

    let chHtml = '<div class="channel-list">';
    (data.channels || []).forEach((c) => {
      const badge = c.enabled
        ? `<span class="badge badge-ok">${t("status.enabled")}</span>`
        : `<span class="badge badge-off">${t("status.disabled")}</span>`;
      chHtml += `<div class="channel-row"><span>${CHANNEL_NAMES[c.name] || c.name}</span>${badge}</div>`;
    });
    chHtml += "</div>";
    html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.channels")}</h3>${chHtml}</div>`;

    if (data.mcp_servers && data.mcp_servers.length) {
      let connBadge;
      if (data.mcp_tool_count > 0) {
        connBadge = `<span class="badge badge-ok" style="margin-left:8px">${t("status.mcpConnected")} (${data.mcp_tool_count} tools)</span>`;
      } else if (data.mcp_connected) {
        connBadge = `<span class="badge badge-off" style="margin-left:8px">${t("status.mcpNoTools")}</span>`;
      } else {
        connBadge = `<span class="badge badge-off" style="margin-left:8px">${t("status.mcpNotConnected")}</span>`;
      }

      let mcpHtml = '<div class="provider-list">';
      data.mcp_servers.forEach((srv) => {
        const logEntry = (data.mcp_log || []).filter(l => l.server === srv.name).slice(-1)[0];
        let statusIcon = "⏳";
        if (logEntry) {
          if (logEntry.level === "ok") statusIcon = "✅";
          else if (logEntry.level === "error") statusIcon = "❌";
          else if (logEntry.level === "warn") statusIcon = "⚠️";
        }
        mcpHtml += `<div class="provider-row"><span>${statusIcon} ${escapeHtml(srv.name)} <span class="mcp-type-badge ${srv.type}" style="font-size:10px;padding:1px 6px;margin-left:4px;">${srv.type}</span></span><span style="font-size:12px;color:var(--text-dim);max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeAttr(srv.detail)}">${escapeHtml(srv.detail)}</span></div>`;
        if (logEntry && logEntry.level === "error") {
          mcpHtml += `<div style="padding:2px 0 6px 28px;font-size:11px;color:var(--red)">${escapeHtml(logEntry.message)}</div>`;
        }
      });
      mcpHtml += "</div>";

      if (data.mcp_tool_names && data.mcp_tool_names.length) {
        mcpHtml += `<details style="margin-top:10px"><summary style="cursor:pointer;font-size:12px;color:var(--text-dim)">${t("status.mcpRegisteredTools")} (${data.mcp_tool_names.length})</summary>`;
        mcpHtml += `<div style="margin-top:6px;font-size:11px;color:var(--text-dim);max-height:200px;overflow:auto;font-family:monospace">`;
        data.mcp_tool_names.forEach(n => { mcpHtml += `<div style="padding:1px 0">${escapeHtml(n)}</div>`; });
        mcpHtml += `</div></details>`;
      }

      if (data.mcp_log && data.mcp_log.length) {
        mcpHtml += `<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--text-dim)">${t("status.mcpLog")} (${data.mcp_log.length})</summary>`;
        mcpHtml += `<div style="margin-top:6px;font-size:11px;max-height:200px;overflow:auto;font-family:monospace;background:var(--bg-dark);padding:8px;border-radius:6px">`;
        data.mcp_log.forEach(l => {
          const color = l.level === "error" ? "var(--red)" : l.level === "ok" ? "var(--green)" : l.level === "warn" ? "var(--yellow)" : "var(--text-dim)";
          mcpHtml += `<div style="padding:1px 0;color:${color}">[${l.level}] ${escapeHtml(l.server)}: ${escapeHtml(l.message)}</div>`;
        });
        mcpHtml += `</div></details>`;
      }

      mcpHtml += `<div style="margin-top:12px;display:flex;gap:8px">`;
      mcpHtml += `<button class="btn btn-sm" onclick="mcpTest()" id="btn-mcp-test">${t("status.mcpTest")}</button>`;
      mcpHtml += `<button class="btn btn-sm btn-primary" onclick="mcpReconnect()" id="btn-mcp-reconnect">${t("status.mcpReconnect")}</button>`;
      mcpHtml += `</div><div id="mcp-test-result" style="margin-top:8px"></div>`;

      html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.mcpTools")} ${connBadge}</h3>${mcpHtml}</div>`;
    }

    try {
      const cases = await api("/api/cases/stats");
      let casesHtml = `<div class="provider-list">
        <div class="provider-row"><span>${t("status.positiveCases")}</span><span class="badge badge-ok">${cases.positive_count}</span></div>
        <div class="provider-row"><span>${t("status.negativeCases")}</span><span class="badge ${cases.negative_count ? 'badge-off' : 'badge-ok'}">${cases.negative_count}</span></div>
      </div>`;
      if (cases.recent_positive.length || cases.recent_negative.length) {
        casesHtml += '<div style="margin-top:12px;font-size:12px;color:var(--text-dim)">';
        if (cases.recent_positive.length) {
          casesHtml += `<div style='margin-bottom:6px;font-weight:500;color:var(--green)'>${t("status.recentPositive")}</div>`;
          cases.recent_positive.forEach((c) => { casesHtml += `<div style="margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">👍 ${escapeHtml(c.prompt)}</div>`; });
        }
        if (cases.recent_negative.length) {
          casesHtml += `<div style='margin-top:8px;margin-bottom:6px;font-weight:500;color:var(--red)'>${t("status.recentNegative")}</div>`;
          cases.recent_negative.forEach((c) => { casesHtml += `<div style="margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">👎 ${escapeHtml(c.prompt)}</div>`; });
        }
        casesHtml += "</div>";
      }
      html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.cases")}</h3>${casesHtml}</div>`;
    } catch (_) {}

    grid.innerHTML = html;
  } catch (e) {
    grid.innerHTML = `<div class="status-card"><div class="status-value err">${t("status.loadFail")}${e.message}</div></div>`;
  }
}

function statusCard(title, value, cls) {
  return `<div class="status-card"><h3>${title}</h3><div class="status-value ${cls}">${escapeHtml(value || "—")}</div></div>`;
}

async function mcpTest() {
  const btn = document.getElementById("btn-mcp-test");
  const box = document.getElementById("mcp-test-result");
  if (!btn || !box) return;
  btn.disabled = true;
  btn.textContent = t("status.mcpTesting");
  box.innerHTML = `<div style="font-size:12px;color:var(--text-dim)">${t("status.mcpTesting")}</div>`;
  try {
    const res = await api("/api/mcp/test", "POST");
    if (res.error) { box.innerHTML = `<div style="color:var(--red);font-size:12px">${escapeHtml(res.error)}</div>`; return; }
    let html = "";
    (res.results || []).forEach(r => {
      const color = r.status === "ok" ? "var(--green)" : "var(--red)";
      const icon = r.status === "ok" ? "✅" : "❌";
      html += `<div style="margin-bottom:6px"><div style="font-weight:500;color:${color}">${icon} ${escapeHtml(r.name)} — ${escapeHtml(r.message)}</div>`;
      if (r.tools && r.tools.length) {
        html += `<div style="font-size:11px;color:var(--text-dim);margin-left:24px;font-family:monospace">${r.tools.join(", ")}</div>`;
      }
      html += `</div>`;
    });
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<div style="color:var(--red);font-size:12px">${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = t("status.mcpTest");
  }
}

async function mcpReconnect() {
  const btn = document.getElementById("btn-mcp-reconnect");
  const box = document.getElementById("mcp-test-result");
  if (!btn || !box) return;
  btn.disabled = true;
  btn.textContent = t("status.mcpReconnecting");
  box.innerHTML = `<div style="font-size:12px;color:var(--text-dim)">${t("status.mcpReconnecting")}</div>`;
  try {
    const res = await api("/api/mcp/reconnect", "POST");
    if (res.error) {
      box.innerHTML = `<div style="color:var(--red);font-size:12px">${escapeHtml(res.error)}</div>`;
      return;
    }
    let html = `<div style="color:var(--green);font-weight:500;margin-bottom:6px">✅ ${res.mcp_tool_count} tools registered</div>`;
    if (res.mcp_log) {
      res.mcp_log.forEach(l => {
        const color = l.level === "error" ? "var(--red)" : l.level === "ok" ? "var(--green)" : l.level === "warn" ? "var(--yellow)" : "var(--text-dim)";
        html += `<div style="font-size:11px;color:${color};font-family:monospace">[${l.level}] ${escapeHtml(l.server)}: ${escapeHtml(l.message)}</div>`;
      });
    }
    box.innerHTML = html;
    setTimeout(() => loadStatus(), 1500);
  } catch (e) {
    box.innerHTML = `<div style="color:var(--red);font-size:12px">${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = t("status.mcpReconnect");
  }
}

// ── Gateway ───────────────────────────────────────────────────────────

let gwPollTimer = null;

async function loadGatewayStatus() {
  try {
    const data = await api("/api/gateway/status");
    updateGatewayUI(data.running);
    if (data.running && !gwPollTimer) startGwPoll();
    if (!data.running && gwPollTimer) stopGwPoll();
  } catch (_) {}
}

function updateGatewayUI(running) {
  document.getElementById("gw-indicator").className = "gateway-indicator " + (running ? "on" : "off");
  document.getElementById("gw-status-text").textContent = running ? t("gw.running") : t("gw.stopped");
  document.getElementById("gw-status-sub").textContent = running ? t("gw.runningDesc") : t("gw.stoppedDesc");
  document.getElementById("gw-start-btn").style.display = running ? "none" : "";
  document.getElementById("gw-stop-btn").style.display = running ? "" : "none";
  document.getElementById("gateway-log").style.display = running ? "block" : "none";
}

async function startGateway() {
  try {
    const res = await api("/api/gateway/start", "POST");
    if (res.success) {
      toast(t("gw.started") + " (PID: " + res.pid + ")", "success");
      updateGatewayUI(true);
      startGwPoll();
    } else { toast(res.error || t("gw.startFail"), "error"); }
  } catch (e) { toast(t("gw.startFail") + ": " + e.message, "error"); }
}

async function stopGateway() {
  try {
    const res = await api("/api/gateway/stop", "POST");
    if (res.success) {
      toast(t("gw.stoppedMsg"), "info");
      updateGatewayUI(false);
      stopGwPoll();
    } else { toast(res.error || t("gw.stopFail"), "error"); }
  } catch (e) { toast(t("gw.stopFail") + ": " + e.message, "error"); }
}

function startGwPoll() {
  stopGwPoll();
  gwPollTimer = setInterval(async () => {
    try {
      const status = await api("/api/gateway/status");
      if (!status.running) { updateGatewayUI(false); stopGwPoll(); return; }
      const data = await api("/api/gateway/logs");
      if (data.logs) { const pre = document.getElementById("gw-log-content"); pre.textContent += data.logs; pre.scrollTop = pre.scrollHeight; }
    } catch (_) {}
  }, 3000);
}

function stopGwPoll() { if (gwPollTimer) { clearInterval(gwPollTimer); gwPollTimer = null; } }

// ── Utilities ─────────────────────────────────────────────────────────

async function api(url, method = "GET", body = null) {
  const opts = { method, headers: authHeaders() };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(url, opts);
  return res.json();
}

function toast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  div.textContent = message;
  container.appendChild(div);
  setTimeout(() => div.remove(), duration);
}

function showConfirm(message, { confirmText, cancelText, danger } = {}) {
  return new Promise(resolve => {
    const overlay = document.getElementById("modal-overlay");
    const body = document.getElementById("modal-body");
    const footer = document.getElementById("modal-footer");

    body.textContent = message;

    const okLabel = confirmText || (_lang === "zh" ? "确定" : "OK");
    const noLabel = cancelText || (_lang === "zh" ? "取消" : "Cancel");

    footer.innerHTML = "";
    const btnCancel = document.createElement("button");
    btnCancel.className = "btn modal-btn-cancel";
    btnCancel.textContent = noLabel;
    const btnOk = document.createElement("button");
    btnOk.className = danger ? "btn btn-danger modal-btn-ok" : "btn btn-primary modal-btn-ok";
    btnOk.textContent = okLabel;
    footer.appendChild(btnCancel);
    footer.appendChild(btnOk);

    overlay.style.display = "";
    requestAnimationFrame(() => overlay.classList.add("modal-visible"));

    function close(result) {
      overlay.classList.remove("modal-visible");
      setTimeout(() => { overlay.style.display = "none"; }, 200);
      resolve(result);
    }

    btnOk.onclick = () => close(true);
    btnCancel.onclick = () => close(false);
    overlay.onclick = (e) => { if (e.target === overlay) close(false); };
  });
}

// ── Voice Input (STT) ────────────────────────────────────────────────
let _recognition = null;
let _voiceActive = false;

function _initSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    const btn = document.getElementById("voice-btn");
    if (btn) btn.classList.add("unsupported");
    return null;
  }
  const rec = new SR();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = _lang === "en" ? "en-US" : "zh-CN";

  rec.onresult = (e) => {
    const input = document.getElementById("chat-input");
    let transcript = "";
    for (let i = 0; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    input.value = transcript;
    input.dispatchEvent(new Event("input"));
  };

  rec.onend = () => {
    _voiceActive = false;
    const btn = document.getElementById("voice-btn");
    if (btn) btn.classList.remove("recording");
    const input = document.getElementById("chat-input");
    if (input && input.value.trim()) {
      sendMessage();
    }
  };

  rec.onerror = (e) => {
    _voiceActive = false;
    const btn = document.getElementById("voice-btn");
    if (btn) btn.classList.remove("recording");
    if (e.error !== "aborted" && e.error !== "no-speech") {
      console.warn("Speech recognition error:", e.error);
    }
  };

  return rec;
}

function toggleVoiceInput() {
  if (!_recognition) _recognition = _initSpeechRecognition();
  if (!_recognition) { toast(t("voice.unsupported"), "error"); return; }

  _recognition.lang = _lang === "en" ? "en-US" : "zh-CN";

  const btn = document.getElementById("voice-btn");
  if (_voiceActive) {
    _recognition.stop();
    _voiceActive = false;
    btn.classList.remove("recording");
  } else {
    _recognition.start();
    _voiceActive = true;
    btn.classList.add("recording");
    toast(t("voice.listening"), "info", 2000);
  }
}

// ── Voice Notification (TTS) ─────────────────────────────────────────
let _ttsVoices = [];

const _PREFERRED_ZH = [
  "Xiaoxiao", "Yunyang", "Xiaoyi", "Yunxi",
  "Xiaoxuan", "Yunfeng", "Xiaomo",
];
const _PREFERRED_EN = [
  "Jenny", "Aria", "Guy", "Sara", "Nancy",
];

function _isTTSEnabled() {
  const v = localStorage.getItem("nanobot_tts");
  return v === null || v === "true";
}

function _loadVoices() {
  if (!window.speechSynthesis) return;
  const populate = () => {
    _ttsVoices = speechSynthesis.getVoices();
    _populateVoiceSelect();
  };
  populate();
  if (!_ttsVoices.length) {
    speechSynthesis.onvoiceschanged = populate;
  }
}

function _populateVoiceSelect() {
  const sel = document.getElementById("tts-voice");
  if (!sel) return;
  sel.innerHTML = "";

  const langPrefix = _lang === "en" ? "en" : "zh";
  const preferred = _lang === "en" ? _PREFERRED_EN : _PREFERRED_ZH;

  const matched = _ttsVoices.filter(v => v.lang.toLowerCase().startsWith(langPrefix));
  const others = _ttsVoices.filter(v => !v.lang.toLowerCase().startsWith(langPrefix));

  const scored = matched.map(v => {
    const name = v.name;
    let score = 0;
    if (/online/i.test(name)) score += 100;
    if (/natural/i.test(name)) score += 80;
    if (/neural/i.test(name)) score += 60;
    const prefIdx = preferred.findIndex(p => name.includes(p));
    if (prefIdx >= 0) score += 50 - prefIdx;
    return { voice: v, score };
  });
  scored.sort((a, b) => b.score - a.score);

  const savedName = localStorage.getItem("nanobot_tts_voice");
  let hasSelected = false;

  scored.forEach(({ voice }) => {
    const opt = document.createElement("option");
    const tag = /online/i.test(voice.name) ? " ✨" : "";
    opt.value = voice.name;
    opt.textContent = _shortVoiceName(voice.name) + tag;
    opt.title = voice.name;
    if (voice.name === savedName) { opt.selected = true; hasSelected = true; }
    sel.appendChild(opt);
  });

  if (others.length) {
    const sep = document.createElement("option");
    sep.disabled = true;
    sep.textContent = "────";
    sel.appendChild(sep);
    others.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v.name;
      opt.textContent = _shortVoiceName(v.name);
      opt.title = v.name;
      if (v.name === savedName) { opt.selected = true; hasSelected = true; }
      sel.appendChild(opt);
    });
  }

  if (!hasSelected && scored.length) {
    sel.value = scored[0].voice.name;
    localStorage.setItem("nanobot_tts_voice", scored[0].voice.name);
  }
}

function _shortVoiceName(name) {
  return name
    .replace(/^Microsoft\s+/i, "")
    .replace(/\s+Online\s*(\(Natural\))?/i, "")
    .replace(/\s*-\s*Chinese.*$/i, "")
    .replace(/\s*-\s*English.*$/i, "");
}

function _getSelectedVoice() {
  const savedName = localStorage.getItem("nanobot_tts_voice");
  if (savedName) {
    const found = _ttsVoices.find(v => v.name === savedName);
    if (found) return found;
  }
  const langPrefix = _lang === "en" ? "en" : "zh";
  const preferred = _lang === "en" ? _PREFERRED_EN : _PREFERRED_ZH;
  const matched = _ttsVoices.filter(v => v.lang.toLowerCase().startsWith(langPrefix));
  for (const p of preferred) {
    const v = matched.find(v => v.name.includes(p) && /online/i.test(v.name));
    if (v) return v;
  }
  for (const p of preferred) {
    const v = matched.find(v => v.name.includes(p));
    if (v) return v;
  }
  return matched[0] || null;
}

function saveVoiceSetting() {
  const sel = document.getElementById("tts-voice");
  if (sel) localStorage.setItem("nanobot_tts_voice", sel.value);
}

function previewVoice() {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const sample = _lang === "en"
    ? "Hello! I'm your assistant, ready to help."
    : "你好！我是你的智能助手，随时为你服务。";
  const utter = new SpeechSynthesisUtterance(sample);
  const voice = _getSelectedVoice();
  if (voice) { utter.voice = voice; utter.lang = voice.lang; }
  else { utter.lang = _lang === "en" ? "en-US" : "zh-CN"; }
  utter.rate = 1.0;
  utter.pitch = 1.0;
  window.speechSynthesis.speak(utter);
}

function saveTTSSetting() {
  const enabled = document.getElementById("tts-enabled").checked;
  localStorage.setItem("nanobot_tts", enabled ? "true" : "false");
  toast(enabled ? t("voice.ttsOn") : t("voice.ttsOff"), "info", 2000);
}

function _loadTTSSetting() {
  const cb = document.getElementById("tts-enabled");
  if (cb) cb.checked = _isTTSEnabled();
  _loadVoices();
}

function speakText(text) {
  if (!_isTTSEnabled() || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const clean = text.replace(/[#*`_~\[\](){}|<>]/g, "");
  let truncated = clean;
  if (clean.length > 60) {
    const cutPoints = /[。！？；\n.!?;]/g;
    let lastCut = 0;
    let m;
    while ((m = cutPoints.exec(clean)) !== null) {
      if (m.index + 1 <= 60) lastCut = m.index + 1;
      else break;
    }
    truncated = lastCut > 0 ? clean.slice(0, lastCut) : clean.slice(0, 60);
  }
  if (!truncated.trim()) return;
  const utter = new SpeechSynthesisUtterance(truncated);
  const voice = _getSelectedVoice();
  if (voice) { utter.voice = voice; utter.lang = voice.lang; }
  else { utter.lang = _lang === "en" ? "en-US" : "zh-CN"; }
  utter.rate = 1.0;
  utter.pitch = 1.0;
  window.speechSynthesis.speak(utter);
}

function stopSpeech() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

// Hook into notification polling to trigger TTS
const _origPollNotifications = pollNotifications;
pollNotifications = async function() {
  try {
    const items = await api("/api/notifications");
    if (!items || !items.length) return;
    items.forEach(n => {
      toast(`🔔 ${n.title}\n${n.content}`, n.level === "error" ? "error" : "success", 8000);
    });
    const last = items[items.length - 1];
    speakText(`${last.title}。${last.content}`);
  } catch (_) {}
};

document.addEventListener("DOMContentLoaded", _loadTTSSetting);

// ── Apps ──────────────────────────────────────────────────────────────

let _appsCache = [];
let _appsSortOrder = "recommended";

async function loadApps() {
  try {
    _appsCache = await api("/api/apps");
  } catch (_) {
    _appsCache = [];
  }
  await updateUnreadBadges();
  const sel = document.getElementById("apps-sort");
  if (sel) _appsSortOrder = sel.value;
  renderApps(_sortApps(_appsCache));
}

function _sortApps(apps) {
  const sorted = [...apps];
  sorted.sort((a, b) => {
    const fa = a.favorite ? 0 : 1;
    const fb = b.favorite ? 0 : 1;
    if (fa !== fb) return fa - fb;
    switch (_appsSortOrder) {
      case "frequency":
        return (b.run_count || 0) - (a.run_count || 0);
      case "created":
        return (b.created_at || "").localeCompare(a.created_at || "");
      case "name":
        return (_appName(a)).localeCompare(_appName(b));
      case "recommended":
      default: {
        const ia = (a.installed || a.type === "custom") ? 0 : 1;
        const ib = (b.installed || b.type === "custom") ? 0 : 1;
        if (ia !== ib) return ia - ib;
        return (b.run_count || 0) - (a.run_count || 0);
      }
    }
  });
  return sorted;
}

function sortApps(order) {
  _appsSortOrder = order;
  const query = (document.getElementById("apps-search")?.value || "").trim();
  const list = query ? _appsCache.filter(a => _appMatchesQuery(a, query)) : _appsCache;
  renderApps(_sortApps(list));
}

function _appMatchesQuery(a, query) {
  const q = query.toLowerCase();
  return (a.name || "").toLowerCase().includes(q) ||
    (a.name_en || "").toLowerCase().includes(q) ||
    (a.description || "").toLowerCase().includes(q) ||
    (a.description_en || "").toLowerCase().includes(q);
}

function filterApps(query) {
  if (!query) { renderApps(_sortApps(_appsCache)); return; }
  const filtered = _appsCache.filter(a => _appMatchesQuery(a, query));
  renderApps(_sortApps(filtered));
}

function _appName(a) { return _lang === "en" ? (a.name_en || a.name) : a.name; }
function _appDesc(a) { return _lang === "en" ? (a.description_en || a.description) : a.description; }

function renderPermTags(permissions) {
  if (!permissions || !permissions.length) return "";
  const permClass = (p) => {
    const cap = p.split(".")[0];
    return `perm-tag perm-${cap}`;
  };
  return `<div class="perm-tags">${permissions.slice(0, 6).map(p =>
    `<span class="${permClass(p)}" title="${p}">${p}</span>`
  ).join("")}${permissions.length > 6 ? `<span class="perm-tag">+${permissions.length - 6}</span>` : ""}</div>`;
}

function renderApps(apps) {
  const grid = document.getElementById("apps-grid");
  if (!apps.length) {
    grid.innerHTML = `<div class="apps-empty">${t("apps.search")}</div>`;
    return;
  }

  // "Create Custom App" card always first
  let html = `<div class="app-card app-card-create" onclick="openCustomAppWizard()">
    <div class="app-card-header"><div class="app-card-icon">➕</div></div>
    <div class="app-card-body">
      <h3 class="app-card-name">${t("custom.create")}</h3>
      <p class="app-card-desc">${t("custom.templateHelp")}</p>
    </div>
  </div>`;

  html += apps.map(a => {
    const name = escapeHtml(_appName(a));
    const desc = escapeHtml(_appDesc(a));
    const ver = escapeHtml(a.version || "1.0.0");
    const icon = a.icon || "📦";
    const isInstalled = a.installed;
    const isEnabled = a.enabled;
    const isCustom = a.type === "custom";
    const comingSoon = a.coming_soon;

    let statusBadge = "";
    let actions = "";

    if (isCustom) {
      statusBadge = `<span class="app-badge app-badge-custom">${t("custom.badge")}</span>`;
      actions = `
        <div class="app-card-actions-right">
          <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteCustomApp('${a.id}')">🗑 ${t("custom.delete")}</button>
        </div>`;
    } else if (comingSoon) {
      statusBadge = `<span class="app-badge app-badge-soon">${t("apps.comingSoon")}</span>`;
    } else if (isInstalled) {
      statusBadge = isEnabled
        ? `<span class="app-badge app-badge-on">${t("apps.enabled")}</span>`
        : `<span class="app-badge app-badge-off">${t("apps.disabled")}</span>`;
      actions = `
        <div class="app-card-actions-right">
          <button class="btn btn-sm btn-danger-subtle" onclick="event.stopPropagation();uninstallApp('${a.id}')">📦 ${t("apps.uninstall")}</button>
        </div>`;
    } else {
      statusBadge = `<span class="app-badge app-badge-new">${t("apps.notInstalled")}</span>`;
      actions = `<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();installApp('${a.id}')">📥 ${t("apps.install")}</button>`;
    }

    const unreadBadge = isCustom ? _appCardBadge(a.id) : "";
    const isFav = a.favorite;
    const favHeart = isFav ? "❤️" : "🤍";
    const favBtn = `<button class="app-fav-btn${isFav ? ' favorited' : ''}" onclick="event.stopPropagation();toggleFavorite('${a.id}')" title="${isFav ? '取消收藏' : '收藏'}">${favHeart}</button>`;

    return `<div class="app-card${isInstalled || isCustom ? ' installed' : ''}${comingSoon ? ' coming-soon' : ''}" onclick="${(isInstalled || isCustom) && !comingSoon ? `openAppDetail('${a.id}')` : ''}">
      <div class="app-card-header">
        <div class="app-card-icon">${icon}${unreadBadge}</div>
        <div class="app-card-header-right">
          ${statusBadge}
          ${favBtn}
        </div>
      </div>
      <div class="app-card-body">
        <h3 class="app-card-name">${name}</h3>
        <p class="app-card-desc">${desc}</p>
        <div class="app-card-meta">
          <span>${isCustom ? t("custom.badge") : t("apps.version") + " " + ver}</span>
          ${a.source ? `<span class="source-badge source-${a.source}">${a.source}</span>` : ""}
          ${_renderModeBadge(a.security_mode || a.min_mode || (isCustom ? "Observer" : ""))}
        </div>
        ${renderPermTags(a.permissions)}
      </div>
      <div class="app-card-actions">${actions}</div>
    </div>`;
  }).join("");

  grid.innerHTML = html;
}

async function toggleFavorite(appId) {
  try {
    const res = await api(`/api/apps/${appId}/favorite`, "POST");
    if (res.success) {
      const app = _appsCache.find(a => a.id === appId);
      if (app) app.favorite = res.favorite;
      const query = (document.getElementById("apps-search")?.value || "").trim();
      const list = query ? _appsCache.filter(a => _appMatchesQuery(a, query)) : _appsCache;
      renderApps(_sortApps(list));
    }
  } catch (_) {}
}

async function installApp(appId) {
  try {
    const res = await api(`/api/apps/${appId}/install`, "POST");
    if (res.success) {
      toast(t("apps.installOk"), "success");
      await loadApps();
    } else {
      toast(res.error || t("apps.installFail"), "error");
    }
  } catch (e) { toast(t("apps.installFail") + ": " + e.message, "error"); }
}

async function uninstallApp(appId) {
  if (!await showConfirm(_lang === "zh" ? "确定要卸载此应用吗？" : "Uninstall this app?", { danger: true })) return;
  try {
    const res = await api(`/api/apps/${appId}/uninstall`, "POST");
    if (res.success) {
      toast(t("apps.uninstallOk"), "info");
      await loadApps();
    } else {
      toast(res.error || t("apps.uninstallFail"), "error");
    }
  } catch (e) { toast(t("apps.uninstallFail") + ": " + e.message, "error"); }
}

// ── App Detail (Daily Digest) ─────────────────────────────────────────

async function openAppDetail(appId) {
  if (appId === "daily_digest") { await openDigestDetail(); return; }
  if (appId === "email_summary") { await openEmailDetail(); return; }
  if (appId.startsWith("capp_")) { await openCustomAppDetail(appId); return; }
  toast("This app has no configuration page yet.", "info");
}

async function openAppReports(appId) {
  await openAppDetail(appId);
  setTimeout(() => {
    const targets = ["digest-report-list", "email-report-list", "capp-report-list",
                     "focus-stats-content"];
    for (const id of targets) {
      const el = document.getElementById(id);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    }
  }, 200);
}

async function openDigestDetail() {
  document.getElementById("app-detail-title").textContent = `🎯 ${t("digest.title")}`;
  switchPage("app-detail");

  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  let appData = _appsCache.find(a => a.id === "daily_digest");
  if (!appData) { await loadApps(); appData = _appsCache.find(a => a.id === "daily_digest"); }
  if (!appData || !appData.installed) {
    container.innerHTML = `<div class="app-detail-loading">${t("apps.notInstalled")}</div>`;
    return;
  }

  const config = appData.config || {};
  const browser = config.browser || "auto";
  const hours = config.history_hours || 24;
  const scheduleTime = config.schedule_time || "22:00";
  const pushNotif = config.push_notification !== false;
  const pushEmail = config.push_email || "";
  const isEnabled = appData.enabled;

  let reportsHtml = "";
  try {
    const reports = await api("/api/apps/daily_digest/reports");
    if (reports.length) {
      reportsHtml = reports.map(r =>
        `<div class="digest-report-item" onclick="viewDigestReport('${escapeAttr(r.date)}')">
          <span class="digest-report-date">📄 ${escapeHtml(r.date)}</span>
          <span class="digest-report-time">${escapeHtml(r.generated_at ? r.generated_at.replace("T", " ").slice(0, 19) : "")}</span>
          <button class="btn btn-sm">${t("digest.viewReport")}</button>
        </div>`
      ).join("");
    } else {
      reportsHtml = `<div class="digest-empty">${t("digest.noReports")}</div>`;
    }
  } catch (_) {
    reportsHtml = `<div class="digest-empty">${t("digest.noReports")}</div>`;
  }

  container.innerHTML = `
    <div class="app-detail-section">
      <div class="digest-status-bar">
        <div class="digest-status-left">
          ${_renderModeBadge("Observer")}
          <span class="digest-status-dot ${isEnabled ? 'on' : 'off'}"></span>
          <span>${t("digest.status")}: <strong>${isEnabled ? t("apps.enabled") : t("apps.disabled")}</strong></span>
        </div>
        <label class="toggle">
          <input type="checkbox" id="digest-enabled" ${isEnabled ? "checked" : ""} onchange="toggleDigestEnabled()" />
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>

    <div class="app-detail-section">
      <h3>${t("digest.config")}</h3>
      <div class="safety-hint" style="margin-bottom:12px">${t("digest.privacyNote")}</div>
      <div class="digest-config-grid">
        <div class="form-group">
          <label>${t("digest.browser")}</label>
          <select id="digest-browser" class="digest-select">
            <option value="auto" ${browser === "auto" ? "selected" : ""}>${t("digest.browserAuto")}</option>
            <option value="chrome" ${browser === "chrome" ? "selected" : ""}>${t("digest.browserChrome")}</option>
            <option value="edge" ${browser === "edge" ? "selected" : ""}>${t("digest.browserEdge")}</option>
          </select>
        </div>
        <div class="form-group">
          <label>${t("digest.historyHours")}</label>
          <input type="number" id="digest-hours" value="${hours}" min="1" max="168" />
        </div>
        <div class="form-group">
          <label>${t("digest.scheduleTime")}</label>
          <input type="time" id="digest-schedule" value="${escapeAttr(scheduleTime)}" />
        </div>
        <div class="form-group">
          <label>${t("digest.pushEmail")}</label>
          <input type="email" id="digest-email" value="${escapeAttr(pushEmail)}" placeholder="user@example.com" />
        </div>
        <div class="form-group form-group-checkbox">
          <label>
            <input type="checkbox" id="digest-push-notif" ${pushNotif ? "checked" : ""} />
            <span>${t("digest.pushNotification")}</span>
          </label>
        </div>
      </div>
      <div class="digest-actions">
        <button class="btn btn-primary" onclick="saveDigestConfig()">${t("digest.saveConfig")}</button>
        <button class="btn btn-primary" id="digest-run-btn" onclick="runDigestNow()">🚀 ${t("digest.runNow")}</button>
      </div>
    </div>

    <div class="app-detail-section">
      <h3>${t("digest.preview")}</h3>
      <p class="digest-preview-desc">${t("digest.previewDesc")}</p>
      <button class="btn btn-sm" id="digest-preview-btn" onclick="previewDigest()">🔍 ${t("digest.previewBtn")}</button>
      <div id="digest-preview-result" class="digest-preview-result"></div>
    </div>

    <div class="app-detail-section">
      <h3>${t("digest.reports")}</h3>
      <div class="digest-report-list" id="digest-report-list">${reportsHtml}</div>
    </div>

    <div class="app-detail-section" id="digest-report-view" style="display:none;">
      <h3 id="digest-report-view-title">${t("digest.latestReport")}</h3>
      <div class="digest-report-content" id="digest-report-content"></div>
    </div>
  `;
}

async function toggleDigestEnabled() {
  const cb = document.getElementById("digest-enabled");
  const enabled = cb.checked;
  const endpoint = enabled ? "enable" : "disable";
  try {
    await api(`/api/apps/daily_digest/${endpoint}`, "POST");
    const app = _appsCache.find(a => a.id === "daily_digest");
    if (app) app.enabled = enabled;
  } catch (_) { cb.checked = !enabled; }
}

async function saveDigestConfig() {
  const config = {
    browser: document.getElementById("digest-browser").value,
    history_hours: parseInt(document.getElementById("digest-hours").value) || 24,
    schedule_time: document.getElementById("digest-schedule").value || "22:00",
    push_notification: document.getElementById("digest-push-notif").checked,
    push_email: document.getElementById("digest-email").value.trim(),
  };
  try {
    const res = await api("/api/apps/daily_digest/config", "POST", config);
    if (res.success) {
      toast(t("digest.configSaved"), "success");
      const app = _appsCache.find(a => a.id === "daily_digest");
      if (app) app.config = config;
    } else {
      toast(res.error || t("digest.configFail"), "error");
    }
  } catch (e) { toast(t("digest.configFail") + ": " + e.message, "error"); }
}

async function runDigestNow() {
  const btn = document.getElementById("digest-run-btn");
  btn.disabled = true;
  btn.textContent = "⏳ " + t("digest.running");

  try {
    const res = await api("/api/apps/daily_digest/run", "POST");
    if (res.error) { toast(res.error, "error"); btn.disabled = false; btn.textContent = "🚀 " + t("digest.runNow"); return; }

    _pollDigestStatus(btn);
  } catch (e) {
    toast(t("digest.generateFail") + ": " + e.message, "error");
    btn.disabled = false;
    btn.textContent = "🚀 " + t("digest.runNow");
  }
}

function _pollDigestStatus(btn) {
  const poll = setInterval(async () => {
    try {
      const status = await api("/api/apps/daily_digest/status");
      if (status.status === "done") {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = "🚀 " + t("digest.runNow");
        const sr = status.result?.stats?.search_results;
        const msg = sr ? `${t("digest.generateOk")} (${sr} ${t("digest.searchResults")})` : t("digest.generateOk");
        toast(msg, "success");

        if (status.result && status.result.report) {
          _showDigestReport(status.result.report);
        }
        _refreshDigestReports();
      } else if (status.status === "error") {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = "🚀 " + t("digest.runNow");
        const msg = status.result?.message || t("digest.generateFail");
        toast(msg, "error");
      } else {
        btn.textContent = "⏳ " + (status.progress || t("digest.running"));
      }
    } catch (_) {}
  }, 2000);

  setTimeout(() => clearInterval(poll), 300000);
}

function _showDigestReport(reportData) {
  const section = document.getElementById("digest-report-view");
  const content = document.getElementById("digest-report-content");
  const title = document.getElementById("digest-report-view-title");
  if (!section || !content) return;

  title.textContent = `🎯 ${reportData.date || ""} ${t("digest.latestReport")}`;
  const raw = reportData.content || "";
  content.innerHTML = raw.trimStart().startsWith("<") ? raw : renderMarkdown(raw);

  _injectExploreButtons(content, reportData);

  section.style.display = "block";
  section.scrollIntoView({ behavior: "smooth" });
}

function _injectExploreButtons(container, reportData) {
  const cards = container.querySelectorAll(".dr-card");
  const items = reportData.items;

  /* Build a flat list from structured items data if available */
  const structuredItems = [];
  if (items && items.sections) {
    for (const sec of items.sections) {
      for (const it of (sec.items || [])) {
        structuredItems.push(it);
      }
    }
  }

  const searchResults = reportData.search_results || {};
  const allResults = [];
  for (const cat of Object.keys(searchResults)) {
    for (const r of searchResults[cat]) {
      allResults.push({...r, _cat: cat});
    }
  }

  cards.forEach((card, idx) => {
    const linkEl = card.querySelector("h3 a");
    if (!linkEl) return;
    const cardUrl = linkEl.href || "";
    const cardTitle = linkEl.textContent || "";

    const tagEl = card.querySelector(".dr-tag");
    const descEl = card.querySelector(".dr-desc");
    const keyword = tagEl ? tagEl.textContent.trim() : "";
    const description = descEl ? descEl.textContent.trim() : "";

    let itemData;
    /* Prefer structured items data (exact match by index or URL) */
    const siByUrl = structuredItems.find(si => si.url && cardUrl && (cardUrl.includes(si.url.replace(/\/$/, "")) || si.url.includes(cardUrl.replace(/\/$/, ""))));
    if (siByUrl) {
      itemData = { title: siByUrl.title, url: siByUrl.url, description: siByUrl.desc || description, query_keyword: siByUrl.tag || keyword };
    } else {
      const matched = allResults.find(r =>
        cardUrl && r.url && (cardUrl.includes(r.url.replace(/\/$/, "")) || r.url.includes(cardUrl.replace(/\/$/, "")))
      );
      itemData = matched
        ? { title: matched.title, url: matched.url, description: matched.description || description, query_keyword: matched.query_keyword || keyword }
        : { title: cardTitle, url: cardUrl, description: description, query_keyword: keyword };
    }

    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-explore-digest";
    btn.textContent = `🚀 ${t("digest.explore")}`;
    btn.onclick = (e) => {
      e.stopPropagation();
      exploreDigestItem(itemData, reportData.date);
    };
    card.appendChild(btn);
  });
}

async function exploreDigestItem(item, dateStr) {
  try {
    const res = await api("/api/apps/daily_digest/explore", "POST", { item, date: dateStr });
    if (res.prompt) {
      switchPage("chat");
      const input = document.getElementById("chat-input");
      if (input) {
        input.value = res.prompt;
        input.focus();
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
  } catch (e) {
    toast(t("digest.exploreFail") + ": " + e.message, "error");
  }
}

async function viewDigestReport(dateStr) {
  try {
    const report = await api(`/api/apps/daily_digest/report/${encodeURIComponent(dateStr)}`);
    if (report.error) { toast(report.error, "error"); return; }
    _showDigestReport(report);
  } catch (e) { toast(e.message, "error"); }
}

async function _refreshDigestReports() {
  try {
    const reports = await api("/api/apps/daily_digest/reports");
    const list = document.getElementById("digest-report-list");
    if (!list) return;
    if (reports.length) {
      list.innerHTML = reports.map(r =>
        `<div class="digest-report-item" onclick="viewDigestReport('${escapeAttr(r.date)}')">
          <span class="digest-report-date">📄 ${escapeHtml(r.date)}</span>
          <span class="digest-report-time">${escapeHtml(r.generated_at ? r.generated_at.replace("T", " ").slice(0, 19) : "")}</span>
          <button class="btn btn-sm">${t("digest.viewReport")}</button>
        </div>`
      ).join("");
    } else {
      list.innerHTML = `<div class="digest-empty">${t("digest.noReports")}</div>`;
    }
  } catch (_) {}
}


// ── Email Summary Detail ──────────────────────────────────────────────

async function openEmailDetail() {
  document.getElementById("app-detail-title").textContent = `📧 ${t("email.title")}`;
  switchPage("app-detail");
  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  let appData = _appsCache.find(a => a.id === "email_summary");
  if (!appData) { await loadApps(); appData = _appsCache.find(a => a.id === "email_summary"); }
  if (!appData || !appData.installed) {
    container.innerHTML = `<div class="app-detail-loading">${t("apps.notInstalled")}</div>`;
    return;
  }

  const config = appData.config || {};
  const isEnabled = appData.enabled;

  let presetsHtml = "";
  try {
    const presets = await api("/api/apps/email_summary/presets");
    presetsHtml = Object.entries(presets).map(([key, p]) =>
      `<button class="btn btn-sm email-preset-btn" onclick="applyEmailPreset('${key}','${p.host}',${p.port})">${key.toUpperCase()}</button>`
    ).join("");
  } catch (_) {}

  let reportsHtml = "";
  try {
    const reports = await api("/api/apps/email_summary/reports");
    if (reports.length) {
      reportsHtml = reports.map(r =>
        `<div class="digest-report-item" onclick="viewEmailReport('${escapeAttr(r.date)}')">
          <span class="digest-report-date">📄 ${escapeHtml(r.date)} (${r.email_count} 封)</span>
          <span class="digest-report-time">${escapeHtml(r.generated_at ? r.generated_at.replace("T"," ").slice(0,19) : "")}</span>
          <button class="btn btn-sm">${t("email.viewReport")}</button>
        </div>`
      ).join("");
    } else {
      reportsHtml = `<div class="digest-empty">${t("email.noReports")}</div>`;
    }
  } catch (_) {
    reportsHtml = `<div class="digest-empty">${t("email.noReports")}</div>`;
  }

  container.innerHTML = `
    <div class="app-detail-section">
      <div class="digest-status-bar">
        <div class="digest-status-left">
          ${_renderModeBadge("Assistant")}
          <span class="digest-status-dot ${isEnabled ? 'on' : 'off'}"></span>
          <span>${t("digest.status")}: <strong>${isEnabled ? t("apps.enabled") : t("apps.disabled")}</strong></span>
        </div>
        <label class="toggle">
          <input type="checkbox" id="email-enabled" ${isEnabled ? "checked" : ""} onchange="toggleAppEnabled('email_summary',this)" />
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>

    <div class="app-detail-section">
      <h3>${t("email.imapConfig")}</h3>
      ${presetsHtml ? `<div class="email-presets"><span>${t("email.presets")}:</span> ${presetsHtml}</div>` : ""}
      <div class="digest-config-grid">
        <div class="form-group"><label>${t("email.host")}</label><input type="text" id="email-host" value="${escapeAttr(config.imap_host || "")}" placeholder="imap.qq.com" /></div>
        <div class="form-group"><label>${t("email.port")}</label><input type="number" id="email-port" value="${config.imap_port || 993}" /></div>
        <div class="form-group"><label>${t("email.user")}</label><input type="text" id="email-user" value="${escapeAttr(config.imap_user || "")}" /></div>
        <div class="form-group"><label>${t("email.password")}</label><input type="password" id="email-password" value="${escapeAttr(config.imap_password || "")}" /></div>
        <div class="form-group form-group-checkbox"><label><input type="checkbox" id="email-ssl" ${config.imap_ssl !== false ? "checked" : ""} /><span>${t("email.ssl")}</span></label></div>
        <div class="form-group"><label>${t("email.folder")}</label><input type="text" id="email-folder" value="${escapeAttr(config.imap_folder || "INBOX")}" /></div>
        <div class="form-group"><label>${t("email.hours")}</label><input type="number" id="email-hours" value="${config.hours || 24}" min="1" max="168" /></div>
        <div class="form-group"><label>${t("email.maxEmails")}</label><input type="number" id="email-max" value="${config.max_emails || 50}" min="1" max="200" /></div>
        <div class="form-group"><label>${t("email.scheduleTime")}</label><input type="time" id="email-schedule" value="${escapeAttr(config.schedule_time || "08:00")}" /></div>
      </div>
      <div class="digest-actions">
        <button class="btn" id="email-test-btn" onclick="testEmailConn()">🔌 ${t("email.testConn")}</button>
        <button class="btn btn-primary" onclick="saveEmailConfig()">${t("email.saveConfig")}</button>
        <button class="btn btn-primary" id="email-run-btn" onclick="runEmailNow()">🚀 ${t("email.runNow")}</button>
      </div>
      <div id="email-test-result" style="margin-top:8px;"></div>
    </div>

    <div class="app-detail-section">
      <h3>${t("email.reports")}</h3>
      <div class="digest-report-list" id="email-report-list">${reportsHtml}</div>
    </div>

    <div class="app-detail-section" id="email-report-view" style="display:none;">
      <h3 id="email-report-view-title">${t("digest.latestReport")}</h3>
      <div class="digest-report-content" id="email-report-content"></div>
    </div>
  `;
}

function applyEmailPreset(key, host, port) {
  document.getElementById("email-host").value = host;
  document.getElementById("email-port").value = port;
  document.getElementById("email-ssl").checked = true;
}

async function saveEmailConfig() {
  const config = {
    imap_host: document.getElementById("email-host").value.trim(),
    imap_port: parseInt(document.getElementById("email-port").value) || 993,
    imap_user: document.getElementById("email-user").value.trim(),
    imap_password: document.getElementById("email-password").value,
    imap_ssl: document.getElementById("email-ssl").checked,
    imap_folder: document.getElementById("email-folder").value.trim() || "INBOX",
    hours: parseInt(document.getElementById("email-hours").value) || 24,
    max_emails: parseInt(document.getElementById("email-max").value) || 50,
    schedule_time: document.getElementById("email-schedule").value || "08:00",
  };
  try {
    const res = await api("/api/apps/email_summary/config", "POST", config);
    if (res.success) toast(t("email.configSaved"), "success");
    else toast(res.error || t("digest.configFail"), "error");
  } catch (e) { toast(e.message, "error"); }
}

async function testEmailConn() {
  const btn = document.getElementById("email-test-btn");
  const box = document.getElementById("email-test-result");
  btn.disabled = true;
  btn.textContent = "⏳ " + t("email.testing");
  // Save config first so the backend can test
  await saveEmailConfig();
  try {
    const res = await api("/api/apps/email_summary/test", "POST");
    if (res.success) {
      box.innerHTML = `<span style="color:var(--green)">✅ ${t("email.testOk")}</span>`;
    } else {
      box.innerHTML = `<span style="color:var(--red)">❌ ${t("email.testFail")}: ${escapeHtml(res.message || "")}</span>`;
    }
  } catch (e) {
    box.innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "🔌 " + t("email.testConn");
  }
}

async function runEmailNow() {
  const btn = document.getElementById("email-run-btn");
  btn.disabled = true;
  btn.textContent = "⏳ " + t("email.running");
  try {
    const res = await api("/api/apps/email_summary/run", "POST");
    if (res.error) { toast(res.error, "error"); btn.disabled = false; btn.textContent = "🚀 " + t("email.runNow"); return; }
    const poll = setInterval(async () => {
      const st = await api("/api/apps/email_summary/status");
      if (!st.running) {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = "🚀 " + t("email.runNow");
        if (st.error) toast(st.error, "error");
        else toast(t("email.configSaved"), "success");
        _refreshEmailReports();
      } else {
        btn.textContent = "⏳ " + (st.progress || t("email.running"));
      }
    }, 2000);
    setTimeout(() => clearInterval(poll), 120000);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "🚀 " + t("email.runNow");
    toast(e.message, "error");
  }
}

async function viewEmailReport(dateStr) {
  try {
    const report = await api(`/api/apps/email_summary/report/${encodeURIComponent(dateStr)}`);
    if (report.error) { toast(report.error, "error"); return; }
    const section = document.getElementById("email-report-view");
    const content = document.getElementById("email-report-content");
    const title = document.getElementById("email-report-view-title");
    title.textContent = `📅 ${report.date || dateStr}`;
    const raw = report.content || "";
    content.innerHTML = raw.trimStart().startsWith("<") ? raw : renderMarkdown(raw);
    section.style.display = "block";
    section.scrollIntoView({ behavior: "smooth" });
  } catch (e) { toast(e.message, "error"); }
}

async function _refreshEmailReports() {
  try {
    const reports = await api("/api/apps/email_summary/reports");
    const list = document.getElementById("email-report-list");
    if (!list) return;
    if (reports.length) {
      list.innerHTML = reports.map(r =>
        `<div class="digest-report-item" onclick="viewEmailReport('${escapeAttr(r.date)}')">
          <span class="digest-report-date">📄 ${escapeHtml(r.date)} (${r.email_count} 封)</span>
          <span class="digest-report-time">${escapeHtml(r.generated_at ? r.generated_at.replace("T"," ").slice(0,19) : "")}</span>
          <button class="btn btn-sm">${t("email.viewReport")}</button>
        </div>`
      ).join("");
    } else {
      list.innerHTML = `<div class="digest-empty">${t("email.noReports")}</div>`;
    }
  } catch (_) {}
}


// ── Common app helpers ────────────────────────────────────────────────

async function toggleAppEnabled(appId, checkbox) {
  const enabled = checkbox.checked;
  const endpoint = enabled ? "enable" : "disable";
  try {
    await api(`/api/apps/${appId}/${endpoint}`, "POST");
    const app = _appsCache.find(a => a.id === appId);
    if (app) app.enabled = enabled;
  } catch (_) { checkbox.checked = !enabled; }
}

async function previewDigest() {
  const btn = document.getElementById("digest-preview-btn");
  const box = document.getElementById("digest-preview-result");
  btn.disabled = true;
  btn.textContent = "⏳ " + t("digest.previewLoading");
  box.innerHTML = `<div class="digest-preview-loading">${t("digest.previewLoading")}</div>`;

  try {
    const data = await api("/api/apps/daily_digest/preview");
    if (data.error) { box.innerHTML = `<div class="digest-preview-error">${escapeHtml(data.error)}</div>`; return; }

    const methodLabel = data.method === "llm" ? "AI" : t("digest.previewRuleBased");
    const chatSessions = data.chat_sessions || 0;
    const chatMessages = data.chat_messages || 0;
    let html = `<div class="digest-preview-stats">
      <div class="digest-stat"><span class="digest-stat-num">${data.raw_count}</span><span class="digest-stat-label">${t("digest.rawCount")}</span></div>
      <div class="digest-stat"><span class="digest-stat-num">${data.filtered_count}</span><span class="digest-stat-label">${t("digest.filteredCount")}</span></div>
      <div class="digest-stat"><span class="digest-stat-num">${chatSessions}/${chatMessages}</span><span class="digest-stat-label">${t("digest.chatCount")}</span></div>
      <div class="digest-stat"><span class="digest-stat-num">${data.keyword_count}</span><span class="digest-stat-label">${t("digest.keywordCount")}</span></div>
      <div class="digest-stat"><span class="digest-stat-num">${methodLabel}</span><span class="digest-stat-label">${t("digest.previewMethod")}</span></div>
    </div>`;

    const cats = [
      { key: "work", emoji: "🧠", label: t("digest.work") },
      { key: "study", emoji: "📚", label: t("digest.study") },
      { key: "life", emoji: "🌿", label: t("digest.life") },
    ];
    html += '<div class="digest-preview-cats">';
    for (const cat of cats) {
      const items = (data.interests && data.interests[cat.key]) || [];
      const queries = (data.queries && data.queries[cat.key]) || [];
      html += `<div class="digest-preview-cat">
        <h4>${cat.emoji} ${cat.label}</h4>
        <div class="digest-keyword-tags">`;
      if (items.length) {
        for (const it of items) {
          const countBadge = it.count ? ` <small>(${it.count})</small>` : "";
          html += `<span class="digest-keyword-tag">${escapeHtml(it.keyword)}${countBadge}</span>`;
        }
      } else {
        html += `<span class="digest-keyword-empty">—</span>`;
      }
      html += `</div>`;
      if (queries.length) {
        html += `<div class="digest-query-tags">`;
        for (const q of queries) {
          html += `<span class="digest-query-tag">🔍 ${escapeHtml(q)}</span>`;
        }
        html += `</div>`;
      }
      html += `</div>`;
    }
    html += "</div>";

    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<div class="digest-preview-error">${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 " + t("digest.previewBtn");
  }
}

// ── Custom Apps ───────────────────────────────────────────────────────

function saveAsCustomApp(botMsgIndex) {
  let userPrompt = "";
  for (let i = botMsgIndex - 1; i >= 0; i--) {
    if (chatMessages[i].role === "user") { userPrompt = chatMessages[i].content; break; }
  }
  if (!userPrompt) { toast("No user prompt found", "error"); return; }
  openCustomAppWizard(userPrompt, sessionId);
}

function openCustomAppWizard(sourcePrompt, sourceSessionId, editData) {
  const existing = document.getElementById("custom-app-wizard");
  if (existing) existing.remove();

  const tpl = sourcePrompt || (editData && editData.prompt_template) || "";
  const ed = editData || {};
  const curFmt = ed.output_format || "text";
  const sched = ed.schedule || {};
  const summ = ed.summary || {};
  const summSched = summ.schedule || {};

  const weekdays = t("custom.weekdays").split(",");
  const dowOptions = weekdays.map((d,i) => `<option value="${i}" ${(sched.day_of_week||0)===i?'selected':''}>${d}</option>`).join("");
  const summDowOptions = weekdays.map((d,i) => `<option value="${i}" ${(summSched.day_of_week||0)===i?'selected':''}>${d}</option>`).join("");

  const overlay = document.createElement("div");
  overlay.id = "custom-app-wizard";
  overlay.className = "wizard-overlay";
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

  overlay.innerHTML = `
    <div class="wizard-panel">
      <div class="wizard-steps">
        <span class="wizard-step active" data-step="1">1. ${t("custom.step1")}</span>
        <span class="wizard-step" data-step="2">2. ${t("custom.step2")}</span>
        <span class="wizard-step" data-step="3">3. ${t("custom.step3")}</span>
      </div>
      <div class="wizard-body">
        <!-- Step 1: Task -->
        <div class="wizard-page" id="wizard-page-1">
          <div class="safety-hint safety-hint-dynamic" style="margin-bottom:12px">🛡️ ${t("custom.safetyNote")}<span id="wizard-mode-badge" class="mode-badge"></span></div>
          <label>${t("custom.template")}</label>
          <p class="wizard-help">${t("custom.templateHelp")}</p>
          <textarea id="wizard-template" class="wizard-textarea" rows="5">${escapeHtml(tpl)}</textarea>
          <div style="margin-top:12px;">
            <label>${t("custom.outputFmt")}</label>
            <select id="wizard-output-format" class="digest-select">
              <option value="report" ${curFmt==='report'?'selected':''}>${t("custom.fmt.report")}</option>
              <option value="notification" ${curFmt==='notification'?'selected':''}>${t("custom.fmt.notification")}</option>
              <option value="text" ${curFmt==='text'?'selected':''}>${t("custom.fmt.text")}</option>
            </select>
          </div>
        </div>
        <!-- Step 2: Schedule & Summary -->
        <div class="wizard-page" id="wizard-page-2" style="display:none;">
          <h4 style="margin:0 0 8px;">${t("custom.schedule")}</h4>
          <div class="form-group form-group-checkbox"><label><input type="checkbox" id="wizard-sched-enabled" ${sched.enabled?'checked':''} onchange="_wizardToggleSchedFields()" /><span>${t("custom.scheduleEnabled")}</span></label></div>
          <div id="wizard-sched-fields" style="${sched.enabled?'':'display:none;'}">
            <div class="digest-config-grid">
              <div class="form-group">
                <label>${t("custom.schedMode")}</label>
                <select id="wizard-sched-mode" class="digest-select" onchange="_wizardSchedModeChange()">
                  <option value="daily" ${(sched.mode||'daily')==='daily'?'selected':''}>${t("custom.sched.daily")}</option>
                  <option value="weekly" ${sched.mode==='weekly'?'selected':''}>${t("custom.sched.weekly")}</option>
                  <option value="monthly" ${sched.mode==='monthly'?'selected':''}>${t("custom.sched.monthly")}</option>
                  <option value="interval" ${sched.mode==='interval'?'selected':''}>${t("custom.sched.interval")}</option>
                </select>
              </div>
              <div class="form-group"><label>${t("custom.scheduleTime")}</label><input type="time" id="wizard-sched-time" value="${escapeAttr(sched.time||'')}" /></div>
              <div class="form-group" id="wizard-sched-dow-group" style="${sched.mode==='weekly'?'':'display:none;'}">
                <label>${t("custom.schedDow")}</label>
                <select id="wizard-sched-dow" class="digest-select">${dowOptions}</select>
              </div>
              <div class="form-group" id="wizard-sched-dom-group" style="${sched.mode==='monthly'?'':'display:none;'}">
                <label>${t("custom.schedDom")}</label>
                <input type="number" id="wizard-sched-dom" min="1" max="31" value="${sched.day_of_month||1}" />
              </div>
              <div class="form-group" id="wizard-sched-interval-group" style="${sched.mode==='interval'?'':'display:none;'}">
                <label>${t("custom.schedInterval")}</label>
                <input type="number" id="wizard-sched-interval" min="1" value="${sched.interval_days||1}" />
              </div>
            </div>
            <div style="margin-top:12px;">
              <label style="font-weight:600;font-size:13px;">${t("custom.catchup")}</label>
              <div style="display:flex;flex-direction:column;gap:6px;margin-top:6px;">
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
                  <input type="radio" name="wizard-catchup-policy" value="LATEST_ONLY" ${(sched.catchup_policy||'LATEST_ONLY')==='LATEST_ONLY'?'checked':''} />
                  <span>${t("custom.catchup.latest")}</span>
                  <span style="color:var(--text-muted);font-size:12px;margin-left:4px;">${t("custom.catchup.latestHelp")}</span>
                </label>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
                  <input type="radio" name="wizard-catchup-policy" value="ALL_MISSED" ${sched.catchup_policy==='ALL_MISSED'?'checked':''} />
                  <span>${t("custom.catchup.all")}</span>
                  <span style="color:var(--text-muted);font-size:12px;margin-left:4px;">${t("custom.catchup.allHelp")}</span>
                </label>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
                  <input type="radio" name="wizard-catchup-policy" value="NONE" ${sched.catchup_policy==='NONE'?'checked':''} />
                  <span>${t("custom.catchup.none")}</span>
                  <span style="color:var(--text-muted);font-size:12px;margin-left:4px;">${t("custom.catchup.noneHelp")}</span>
                </label>
              </div>
              <details style="margin-top:8px;">
                <summary style="cursor:pointer;font-size:12px;color:var(--text-muted);">${t("custom.catchup.advanced")}</summary>
                <div class="digest-config-grid" style="margin-top:6px;">
                  <div class="form-group">
                    <label>${t("custom.catchup.window")}</label>
                    <select id="wizard-catchup-window" class="digest-select">
                      <option value="24" ${(sched.catchup_window_hours||24)===24?'selected':''}>${t("custom.catchup.window24")}</option>
                      <option value="168" ${sched.catchup_window_hours===168?'selected':''}>${t("custom.catchup.window168")}</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>${t("custom.catchup.maxRuns")}</label>
                    <select id="wizard-catchup-max" class="digest-select">
                      <option value="1" ${(sched.max_catchup_runs||1)===1?'selected':''}>1</option>
                      <option value="2" ${sched.max_catchup_runs===2?'selected':''}>2</option>
                      <option value="3" ${sched.max_catchup_runs===3?'selected':''}>3</option>
                    </select>
                  </div>
                </div>
              </details>
            </div>
          </div>
          <hr style="border:0;border-top:1px solid var(--bg-surface1);margin:16px 0;" />
          <h4 style="margin:0 0 8px;">${t("custom.summary")}</h4>
          <div class="form-group form-group-checkbox"><label><input type="checkbox" id="wizard-summ-enabled" ${summ.enabled?'checked':''} onchange="_wizardToggleSummFields()" /><span>${t("custom.summaryEnabled")}</span></label></div>
          <div id="wizard-summ-fields" style="${summ.enabled?'':'display:none;'}">
            <div class="form-group">
              <label>${t("custom.summaryPrompt")}</label>
              <p class="wizard-help">${t("custom.summaryPromptHelp")}</p>
              <textarea id="wizard-summ-prompt" class="wizard-textarea" rows="3">${escapeHtml(summ.prompt||'')}</textarea>
            </div>
            <div class="digest-config-grid">
              <div class="form-group">
                <label>${t("custom.summaryFormat")}</label>
                <select id="wizard-summ-format" class="digest-select">
                  <option value="html" ${(summ.output_format||'html')==='html'?'selected':''}>${t("custom.summaryFmtHtml")}</option>
                  <option value="text" ${summ.output_format==='text'?'selected':''}>${t("custom.summaryFmtText")}</option>
                </select>
              </div>
              <div class="form-group">
                <label>${t("custom.summaryRange")}</label>
                <div style="display:flex;gap:6px;align-items:center;">
                  <input type="number" id="wizard-summ-range-val" min="1" max="365" value="${summ.range_days ? _rangeToDU(summ.range_days).val : 7}" style="width:70px;" />
                  <select id="wizard-summ-range-unit" class="digest-select" style="width:auto;">
                    <option value="days" ${!summ.range_days || _rangeToDU(summ.range_days).unit==='days' ? 'selected' : ''}>${t("custom.summaryRangeDays")}</option>
                    <option value="weeks" ${summ.range_days && _rangeToDU(summ.range_days).unit==='weeks' ? 'selected' : ''}>${t("custom.summaryRangeWeeks")}</option>
                    <option value="months" ${summ.range_days && _rangeToDU(summ.range_days).unit==='months' ? 'selected' : ''}>${t("custom.summaryRangeMonths")}</option>
                  </select>
                </div>
              </div>
            </div>
            <div class="form-group form-group-checkbox"><label><input type="checkbox" id="wizard-summ-sched-enabled" ${summSched.enabled?'checked':''} /><span>${t("custom.summarySchedule")}</span></label></div>
            <div class="digest-config-grid">
              <div class="form-group">
                <label>${t("custom.schedMode")}</label>
                <select id="wizard-summ-mode" class="digest-select" onchange="_wizardSummSchedModeChange()">
                  <option value="daily" ${(summSched.mode||'daily')==='daily'?'selected':''}>${t("custom.sched.daily")}</option>
                  <option value="weekly" ${summSched.mode==='weekly'?'selected':''}>${t("custom.sched.weekly")}</option>
                  <option value="monthly" ${summSched.mode==='monthly'?'selected':''}>${t("custom.sched.monthly")}</option>
                </select>
              </div>
              <div class="form-group"><label>${t("custom.scheduleTime")}</label><input type="time" id="wizard-summ-time" value="${escapeAttr(summSched.time||'')}" /></div>
              <div class="form-group" id="wizard-summ-dow-group" style="${summSched.mode==='weekly'?'':'display:none;'}">
                <label>${t("custom.schedDow")}</label>
                <select id="wizard-summ-dow" class="digest-select">${summDowOptions}</select>
              </div>
              <div class="form-group" id="wizard-summ-dom-group" style="${summSched.mode==='monthly'?'':'display:none;'}">
                <label>${t("custom.schedDom")}</label>
                <input type="number" id="wizard-summ-dom" min="1" max="31" value="${summSched.day_of_month||1}" />
              </div>
            </div>
          </div>
        </div>
        <!-- Step 3: Info + Security Mode -->
        <div class="wizard-page" id="wizard-page-3" style="display:none;">
          <div class="form-group"><label>${t("custom.name")}</label><input type="text" id="wizard-name" value="${escapeAttr(ed.name || '')}" placeholder="${_lang === "zh" ? "例：每日AI新闻" : "e.g. Daily AI News"}" /></div>
          <div class="form-group"><label>${t("custom.icon")}</label><input type="text" id="wizard-icon" value="${escapeAttr(ed.icon || '🤖')}" maxlength="4" style="width:60px;font-size:24px;text-align:center;" /></div>
          <hr style="border:0;border-top:1px solid var(--bg-surface1);margin:16px 0;" />
          <div class="form-group">
            <label>🛡️ ${t("custom.securityMode")}</label>
            <p class="wizard-help">${t("custom.securityModeHint")}</p>
            <select id="wizard-security-mode" class="digest-select" onchange="_wizardSecurityModeChange()">
              <option value="inherit" ${!ed.security_mode ? 'selected' : ''}>${t("custom.securityModeInherit")}</option>
              <option value="Observer" ${ed.security_mode==='Observer' ? 'selected' : ''}>${_modeWithDesc("Observer")}</option>
              <option value="Assistant" ${ed.security_mode==='Assistant' ? 'selected' : ''}>${_modeWithDesc("Assistant")}</option>
              <option value="Operator" ${ed.security_mode==='Operator' ? 'selected' : ''}>${_modeWithDesc("Operator")}</option>
            </select>
            <div id="wizard-mode-escalation" class="escalation-info" style="display:none;"></div>
          </div>
        </div>
      </div>
      <div class="wizard-footer">
        <button class="btn" id="wizard-prev-btn" onclick="_wizardPrev()" style="display:none;">${t("custom.prev")}</button>
        <button class="btn" onclick="document.getElementById('custom-app-wizard').remove()">${t("custom.cancel")}</button>
        <button class="btn btn-primary" id="wizard-next-btn" onclick="_wizardNext()">${t("custom.next")}</button>
      </div>
    </div>
  `;
  overlay._step = 1;
  overlay._editId = ed.id || "";
  document.body.appendChild(overlay);
  _loadSecurityModeBadge("wizard-mode-badge");
}

async function _loadSecurityModeBadge(elementId) {
  try {
    const data = await api("/api/security/mode");
    const mode = data.mode || data.name || "Unknown";
    const desc = _modeShortDesc(mode);
    const name = _modeName(mode);
    const label = desc ? `${name}·${desc}` : name;
    const modeColors = { Observer: "#6c757d", Assistant: "#0d6efd", Operator: "#fd7e14", Developer: "#dc3545" };
    const color = modeColors[mode] || "#6c757d";
    const els = elementId
      ? [document.getElementById(elementId)]
      : document.querySelectorAll(".detail-mode-badge");
    els.forEach(el => {
      if (!el) return;
      el.textContent = label;
      el.style.cssText = `display:inline-block;margin-left:8px;padding:2px 8px;border-radius:10px;font-size:12px;color:#fff;background:${color}`;
    });
  } catch (_) {}
}

async function _wizardSecurityModeChange() {
  const sel = document.getElementById("wizard-security-mode");
  const infoDiv = document.getElementById("wizard-mode-escalation");
  if (!sel || !infoDiv) return;

  const target = sel.value;
  if (target === "inherit") {
    infoDiv.style.display = "none";
    infoDiv.innerHTML = "";
    return;
  }

  try {
    const globalData = await api("/api/security/mode");
    const globalMode = globalData.mode;
    const modeOrder = ["Observer", "Assistant", "Operator", "Developer"];
    const isEsc = modeOrder.indexOf(target) > modeOrder.indexOf(globalMode);

    if (!isEsc) {
      infoDiv.style.display = "block";
      infoDiv.className = "escalation-info escalation-ok";
      const noEscMsg = t("custom.escalation.noEsc")
        .replace("{target}", _modeWithDesc(target))
        .replace("{global}", _modeWithDesc(globalMode));
      infoDiv.innerHTML = `<span class="escalation-icon">✅</span> ${noEscMsg}`;
      return;
    }

    const res = await api(`/api/security/app/_preview/mode`, "POST", { mode: target, confirmed: false });
    const assess = res.assessment || res;

    const riskColors = { low: "#198754", medium: "#fd7e14", high: "#dc3545", critical: "#6f42c1" };
    const riskLabels = { low: t("custom.escalation.risk.low"), medium: t("custom.escalation.risk.medium"),
                         high: t("custom.escalation.risk.high"), critical: t("custom.escalation.risk.critical") };
    const riskColor = riskColors[assess.risk_level] || "#6c757d";
    const riskLabel = riskLabels[assess.risk_level] || assess.risk_level;

    let warningsHtml = "";
    if (assess.warnings && assess.warnings.length) {
      warningsHtml = `<div class="escalation-warnings"><strong>⚠️ ${t("custom.escalation.warnings")}:</strong><ul>${
        assess.warnings.map(w => `<li>${w}</li>`).join("")}</ul></div>`;
    }
    let gainedHtml = "";
    if (assess.capabilities_gained && assess.capabilities_gained.length) {
      gainedHtml = `<div class="escalation-gained"><strong>${t("custom.escalation.gained")}:</strong> ${
        assess.capabilities_gained.join("、")}</div>`;
    }

    infoDiv.style.display = "block";
    infoDiv.className = "escalation-info escalation-warn";
    infoDiv.innerHTML = `
      <div class="escalation-header">
        <span class="escalation-icon">⚠️</span>
        <strong>${t("custom.escalation.title")}</strong>
        <span class="escalation-risk-badge" style="background:${riskColor}">${riskLabel}</span>
      </div>
      <div class="escalation-detail">
        ${t("custom.escalation.from")}: <strong>${_modeWithDesc(globalMode)}</strong>
        <br/>→ ${t("custom.escalation.to")}: <strong>${_modeWithDesc(target)}</strong>
      </div>
      ${gainedHtml}
      ${warningsHtml}
    `;
  } catch (_) {
    infoDiv.style.display = "none";
  }
}

function _rangeToDU(days) {
  if (days >= 30 && days % 30 === 0) return { val: days / 30, unit: "months" };
  if (days >= 7 && days % 7 === 0) return { val: days / 7, unit: "weeks" };
  return { val: days, unit: "days" };
}
function _duToRangeDays(val, unit) {
  if (unit === "months") return val * 30;
  if (unit === "weeks") return val * 7;
  return val;
}
function _rangeToDULabel(days) {
  const d = _rangeToDU(days);
  return `${d.val} ${t("custom.summaryRange" + d.unit.charAt(0).toUpperCase() + d.unit.slice(1))}`;
}

function _wizardToggleSchedFields() {
  const on = document.getElementById("wizard-sched-enabled").checked;
  document.getElementById("wizard-sched-fields").style.display = on ? "" : "none";
}

function _wizardToggleSummFields() {
  const on = document.getElementById("wizard-summ-enabled").checked;
  document.getElementById("wizard-summ-fields").style.display = on ? "" : "none";
}

function _wizardSummSchedModeChange() {
  const mode = document.getElementById("wizard-summ-mode").value;
  document.getElementById("wizard-summ-dow-group").style.display = mode === "weekly" ? "" : "none";
  document.getElementById("wizard-summ-dom-group").style.display = mode === "monthly" ? "" : "none";
}

function _wizardSchedModeChange() {
  const mode = document.getElementById("wizard-sched-mode").value;
  document.getElementById("wizard-sched-dow-group").style.display = mode === "weekly" ? "" : "none";
  document.getElementById("wizard-sched-dom-group").style.display = mode === "monthly" ? "" : "none";
  document.getElementById("wizard-sched-interval-group").style.display = mode === "interval" ? "" : "none";
}

function _wizardGoTo(step) {
  const overlay = document.getElementById("custom-app-wizard");
  if (!overlay) return;
  overlay._step = step;
  for (let i = 1; i <= 3; i++) {
    document.getElementById(`wizard-page-${i}`).style.display = i === step ? "" : "none";
    const stepEl = overlay.querySelector(`.wizard-step[data-step="${i}"]`);
    stepEl.classList.toggle("active", i === step);
    stepEl.classList.toggle("done", i < step);
  }
  document.getElementById("wizard-prev-btn").style.display = step > 1 ? "" : "none";
  document.getElementById("wizard-next-btn").textContent = step < 3 ? t("custom.next") : t("custom.save");
}

function _wizardNext() {
  const overlay = document.getElementById("custom-app-wizard");
  if (!overlay) return;
  if (overlay._step === 1) {
    const tpl = document.getElementById("wizard-template").value.trim();
    if (!tpl) { toast(_lang === "zh" ? "任务描述不能为空" : "Task description required", "error"); return; }
  }
  if (overlay._step < 3) {
    _wizardGoTo(overlay._step + 1);
  } else {
    _wizardSave();
  }
}

function _wizardPrev() {
  const overlay = document.getElementById("custom-app-wizard");
  if (!overlay) return;
  if (overlay._step > 1) _wizardGoTo(overlay._step - 1);
}

function _modeName(mode) {
  return t("security.modeName." + mode) || mode;
}
function _modeShortDesc(mode) {
  return t("security.shortDesc." + mode) || "";
}
function _modeWithDesc(mode) {
  const name = _modeName(mode);
  const desc = _modeShortDesc(mode);
  return desc ? `${name} — ${desc}` : name;
}
const _MODE_COLORS = { Observer: "#40a02b", Assistant: "#1e66f5", Operator: "#df8e1d", Developer: "#dc3545" };
function _renderModeBadge(mode) {
  if (!mode) return "";
  const name = _modeName(mode);
  const color = _MODE_COLORS[mode] || "#6c757d";
  return `<span class="security-mode-badge" style="color:${color};border-color:${color};">🛡️ ${name}</span>`;
}

function _showEscalationConfirm(fromMode, toMode) {
  return new Promise(async (resolve) => {
    let assess = {};
    try {
      const res = await api("/api/security/app/_preview/mode", "POST", { mode: toMode });
      assess = res.assessment || {};
    } catch (_) {}

    const riskColors = { low: "#198754", medium: "#fd7e14", high: "#dc3545", critical: "#6f42c1" };
    const riskLabels = { low: t("custom.escalation.risk.low"), medium: t("custom.escalation.risk.medium"),
                         high: t("custom.escalation.risk.high"), critical: t("custom.escalation.risk.critical") };
    const rc = riskColors[assess.risk_level] || "#6c757d";
    const rl = riskLabels[assess.risk_level] || "";

    const gained = (assess.capabilities_gained || []).map(c => `<li>${c}</li>`).join("");
    const warns = (assess.warnings || []).map(w => `<li>${w}</li>`).join("");

    const modal = document.createElement("div");
    modal.className = "modal-overlay";
    modal.innerHTML = `
      <div class="modal-card" style="max-width:480px;">
        <h3 style="margin:0 0 12px;display:flex;align-items:center;gap:8px;">
          <span style="font-size:24px;">⚠️</span>
          ${t("custom.escalation.title")}
          <span style="background:${rc};color:#fff;padding:2px 10px;border-radius:10px;font-size:13px;">${rl}</span>
        </h3>
        <div style="margin-bottom:12px;">
          ${t("custom.escalation.from")}: <strong>${_modeWithDesc(fromMode)}</strong>
          <br/>→ ${t("custom.escalation.to")}: <strong>${_modeWithDesc(toMode)}</strong>
        </div>
        ${gained ? `<div style="margin-bottom:12px;">
          <strong>${t("custom.escalation.gained")}:</strong>
          <ul style="margin:4px 0 0 20px;padding:0;">${gained}</ul>
        </div>` : ""}
        ${warns ? `<div style="margin-bottom:12px;color:var(--text-danger,#dc3545);">
          <strong>${t("custom.escalation.warnings")}:</strong>
          <ul style="margin:4px 0 0 20px;padding:0;">${warns}</ul>
        </div>` : ""}
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:16px;">
          <button class="btn" id="esc-cancel-btn">${t("custom.escalation.cancel")}</button>
          <button class="btn btn-danger" id="esc-confirm-btn">${t("custom.escalation.confirm")}</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector("#esc-cancel-btn").onclick = () => { modal.remove(); resolve(false); };
    modal.querySelector("#esc-confirm-btn").onclick = () => { modal.remove(); resolve(true); };
    modal.onclick = (e) => { if (e.target === modal) { modal.remove(); resolve(false); } };
  });
}

async function _wizardSave() {
  const overlay = document.getElementById("custom-app-wizard");
  if (!overlay) return;
  const template = document.getElementById("wizard-template").value.trim();
  const name = document.getElementById("wizard-name").value.trim();
  const icon = document.getElementById("wizard-icon").value.trim() || "🤖";
  const outputFormat = document.getElementById("wizard-output-format").value;
  if (!template) { toast(_lang === "zh" ? "任务描述不能为空" : "Task description required", "error"); return; }
  if (!name) { toast(_lang === "zh" ? "请输入应用名称" : "Name required", "error"); return; }

  const catchupPolicyEl = document.querySelector('input[name="wizard-catchup-policy"]:checked');
  const schedule = {
    enabled: document.getElementById("wizard-sched-enabled").checked,
    mode: document.getElementById("wizard-sched-mode").value,
    time: document.getElementById("wizard-sched-time").value,
    day_of_week: parseInt(document.getElementById("wizard-sched-dow").value) || 0,
    day_of_month: parseInt(document.getElementById("wizard-sched-dom").value) || 1,
    interval_days: parseInt(document.getElementById("wizard-sched-interval").value) || 1,
    catchup_policy: catchupPolicyEl ? catchupPolicyEl.value : "LATEST_ONLY",
    catchup_window_hours: parseInt(document.getElementById("wizard-catchup-window")?.value) || 24,
    max_catchup_runs: parseInt(document.getElementById("wizard-catchup-max")?.value) || 1,
  };

  const summRangeVal = parseInt(document.getElementById("wizard-summ-range-val")?.value) || 7;
  const summRangeUnit = document.getElementById("wizard-summ-range-unit")?.value || "days";
  const summary = {
    enabled: document.getElementById("wizard-summ-enabled").checked,
    prompt: document.getElementById("wizard-summ-prompt").value.trim(),
    output_format: document.getElementById("wizard-summ-format")?.value || "html",
    range_days: _duToRangeDays(summRangeVal, summRangeUnit),
    schedule: {
      enabled: document.getElementById("wizard-summ-sched-enabled").checked,
      mode: document.getElementById("wizard-summ-mode").value,
      time: document.getElementById("wizard-summ-time").value,
      day_of_week: parseInt(document.getElementById("wizard-summ-dow")?.value) || 0,
      day_of_month: parseInt(document.getElementById("wizard-summ-dom")?.value) || 1,
    },
  };

  const btn = document.getElementById("wizard-next-btn");
  btn.disabled = true;
  btn.textContent = t("custom.saving");

  const securityModeSel = document.getElementById("wizard-security-mode");
  const securityModeVal = securityModeSel ? securityModeSel.value : "inherit";
  const securityMode = securityModeVal === "inherit" ? null : securityModeVal;

  const payload = {
    name, icon,
    prompt_template: template, output_format: outputFormat,
    schedule, summary, security_mode: securityMode,
  };

  try {
    if (securityMode) {
      const globalData = await api("/api/security/mode");
      const globalMode = globalData.mode;
      const modeOrder = ["Observer", "Assistant", "Operator", "Developer"];
      if (modeOrder.indexOf(securityMode) > modeOrder.indexOf(globalMode)) {
        const confirmed = await _showEscalationConfirm(globalMode, securityMode);
        if (!confirmed) {
          btn.disabled = false;
          btn.textContent = t("custom.save");
          return;
        }
      }
    }

    let res;
    const appId = overlay._editId;
    if (appId) {
      res = await api(`/api/apps/custom/${appId}`, "PUT", payload);
    } else {
      res = await api("/api/apps/custom", "POST", payload);
    }
    if (res.error) { toast(res.error, "error"); btn.disabled = false; btn.textContent = t("custom.save"); return; }

    const savedAppId = appId || res.id;
    if (securityMode && savedAppId) {
      try {
        await api(`/api/security/app/${savedAppId}/mode`, "POST",
                  { mode: securityMode, confirmed: true });
      } catch (_) {}
    }

    toast(t("custom.saved"), "success");
    overlay.remove();
    await loadApps();
    if (appId) {
      openCustomAppDetail(appId);
    } else {
      switchPage("apps");
    }
  } catch (e) {
    toast(e.message, "error");
    btn.disabled = false;
    btn.textContent = t("custom.save");
  }
}

async function deleteCustomApp(appId) {
  if (!await showConfirm(_lang === "zh" ? "确定删除此自定义应用？" : "Delete this custom app?", { danger: true })) return;
  try {
    const res = await api(`/api/apps/custom/${appId}`, "DELETE");
    if (res.success) { toast(t("apps.uninstallOk"), "info"); await loadApps(); }
    else toast(res.error || "Delete failed", "error");
  } catch (e) { toast(e.message, "error"); }
}

// ── Custom App Detail Page ────────────────────────────────────────────

function _scheduleDesc(sched) {
  if (!sched || !sched.enabled) return t("apps.disabled");
  const mode = sched.mode || "daily";
  const time = sched.time || "--:--";
  const weekdays = t("custom.weekdays").split(",");
  let desc;
  if (mode === "daily") desc = `${t("custom.sched.daily")} ${time}`;
  else if (mode === "weekly") desc = `${t("custom.sched.weekly")} ${weekdays[sched.day_of_week||0]} ${time}`;
  else if (mode === "monthly") desc = `${t("custom.sched.monthly")} ${sched.day_of_month||1}${_lang==="zh"?"号":"th"} ${time}`;
  else if (mode === "interval") desc = `${_lang==="zh"?"每":"Every "}${sched.interval_days||1}${_lang==="zh"?"天":"d"} ${time}`;
  else desc = time;
  const policy = sched.catchup_policy || "LATEST_ONLY";
  if (policy !== "NONE") {
    const tag = policy === "ALL_MISSED"
      ? (_lang === "zh" ? "补齐" : "catch-up:all")
      : (_lang === "zh" ? "智能补偿" : "catch-up");
    desc += ` <span style="font-size:11px;color:var(--accent);opacity:0.85;">[${tag}]</span>`;
  }
  return desc;
}

async function openCustomAppDetail(appId) {
  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  let capp;
  try { capp = await api(`/api/apps/custom/${appId}`); } catch (_) {}
  if (!capp || capp.error) {
    container.innerHTML = `<div class="app-detail-loading">${t("apps.notInstalled")}</div>`;
    return;
  }

  document.getElementById("app-detail-title").textContent = `${capp.icon || "🤖"} ${capp.name}`;
  switchPage("app-detail");

  const sched = capp.schedule || {};
  const outputFmt = capp.output_format || "text";
  const fmtLabels = {report:t("custom.fmt.report"), notification:t("custom.fmt.notification"), text:t("custom.fmt.text")};
  const summCfg = capp.summary || {};

  const paramDefs = capp.parameters || [];
  _cappParamDefs = paramDefs;
  const hasParams = paramDefs.length > 0;
  let paramGroups = capp.param_groups || [];
  if (hasParams && !paramGroups.length) {
    const fallback = capp.param_values || {};
    paramGroups = [Object.fromEntries(paramDefs.map(p => [p.name, fallback[p.name] || p.default || ""]))];
  }
  let paramsHtml = "";
  if (hasParams) {
    paramsHtml = `<div id="capp-param-groups">${paramGroups.map((g, i) => _paramGroupHtml(paramDefs, g, i, paramGroups.length)).join("")}</div>
      <button class="btn btn-sm" style="margin-top:8px;" onclick="_cappAddGroup()">➕ ${t("custom.addGroup")}</button>`;
  }

  let reportsHtml = "";
  let summariesHtml = "";
  try {
    const reports = await api(`/api/apps/custom/${appId}/reports`);
    const runs = reports.filter(r => (r.type||"run") === "run");
    const summs = reports.filter(r => r.type === "summary");
    if (runs.length) {
      reportsHtml = runs.map(r => _reportItemHtml(appId, r, "📄")).join("");
    } else {
      reportsHtml = `<div class="digest-empty">${t("custom.noReports")}</div>`;
    }
    if (summs.length) {
      summariesHtml = summs.map(r => _reportItemHtml(appId, r, "📊")).join("");
    }
  } catch (_) {
    reportsHtml = `<div class="digest-empty">${t("custom.noReports")}</div>`;
  }

  const fmtBadge = outputFmt !== "text" ? `<span class="app-badge">${fmtLabels[outputFmt]||outputFmt}</span>` : "";

  container.innerHTML = `
    <div class="app-detail-section">
      <div class="digest-status-bar">
        <div class="digest-status-left">
          ${fmtBadge}
          ${_renderModeBadge(capp.security_mode || "Observer")}
          <span class="digest-status-dot ${sched.enabled ? 'on' : 'off'}"></span>
          <span>${t("custom.schedule")}: <strong>${_scheduleDesc(sched)}</strong></span>
        </div>
        <div>
          <button class="btn btn-sm" onclick="openCustomAppWizardEdit('${appId}')">${t("custom.edit")}</button>
          <button class="btn btn-sm btn-danger" onclick="deleteCustomApp('${appId}')">${t("custom.delete")}</button>
        </div>
      </div>
    </div>

    <div class="app-detail-section">
      <div class="safety-hint safety-hint-dynamic" style="margin-bottom:8px">🛡️ ${t("custom.safetyNote")}<span class="mode-badge detail-mode-badge"></span></div>
      <h3>${t("custom.template")}</h3>
      <div class="custom-template-preview">${escapeHtml(capp.prompt_template)}</div>
    </div>

    ${paramsHtml ? `<div class="app-detail-section">
      <h3>${_lang === "zh" ? "参数" : "Parameters"}</h3>
      <div class="digest-config-grid">${paramsHtml}</div>
    </div>` : ""}

    <div class="app-detail-section">
      <h3>🚀 ${_lang === "zh" ? "执行" : "Run"}</h3>
      <div class="digest-actions">
        <button class="btn btn-primary" id="capp-run-btn" data-app-id="${appId}" onclick="runCustomApp('${appId}')">🚀 ${t("custom.run")}</button>
      </div>
      <div class="capp-run-log" id="capp-run-log" style="display:none;"></div>
    </div>

    <div class="app-detail-section">
      <h3>📄 ${t("custom.reports")}</h3>
      <div class="digest-report-list" id="capp-report-list">${reportsHtml}</div>
    </div>

    ${summCfg.enabled ? `<div class="app-detail-section capp-summary-section">
      <h3>📊 ${t("custom.summaries")}</h3>
      <div class="digest-status-bar" style="margin-bottom:12px;">
        <div class="digest-status-left">
          <span class="app-badge">${(summCfg.output_format||'html')==='html' ? t("custom.summaryFmtHtml") : t("custom.summaryFmtText")}</span>
          <span class="app-badge">${t("custom.summaryRange")}: ${_rangeToDULabel(summCfg.range_days || 7)}</span>
        </div>
        <button class="btn" id="capp-summ-btn" onclick="runCustomSummary('${appId}')">📊 ${t("custom.summaryRun")}</button>
      </div>
      <div class="capp-run-log" id="capp-summ-log" style="display:none;"></div>
      <div class="digest-report-list" id="capp-summary-list">${summariesHtml || `<div class="digest-empty">${_lang === "zh" ? "暂无总结报告" : "No summaries yet"}</div>`}</div>
    </div>` : ""}

    <div class="app-detail-section" id="capp-report-view" style="display:none;">
      <h3 id="capp-report-view-title">${t("digest.latestReport")}</h3>
      <div class="digest-report-content" id="capp-report-content"></div>
    </div>
  `;
  _loadSecurityModeBadge(null);
}

// ── Param group helpers ────────────────────────────────────────────
let _cappParamDefs = [];

function _paramGroupHtml(paramDefs, groupVals, idx, total) {
  const label = t("custom.group").replace("{n}", idx + 1);
  const removeBtn = total > 1
    ? `<button class="btn btn-sm btn-danger-subtle" onclick="_cappRemoveGroup(${idx})" title="${t("custom.removeGroup")}">✕</button>`
    : "";
  let fields = "";
  for (const p of paramDefs) {
    const val = groupVals[p.name] !== undefined ? groupVals[p.name] : (p.default || "");
    fields += `<div class="form-group"><label>${escapeHtml(p.label || p.name)}</label><input type="text" class="capp-group-input" data-group="${idx}" data-param="${escapeAttr(p.name)}" value="${escapeAttr(val)}" /></div>`;
  }
  return `<div class="capp-param-group" data-group-idx="${idx}">
    <div class="capp-param-group-header"><span class="capp-param-group-label">${label}</span>${removeBtn}</div>
    <div class="digest-config-grid">${fields}</div>
  </div>`;
}

function _cappCollectGroups() {
  const container = document.getElementById("capp-param-groups");
  if (!container) return [];
  const groups = [];
  container.querySelectorAll(".capp-param-group").forEach(el => {
    const g = {};
    el.querySelectorAll(".capp-group-input").forEach(inp => {
      g[inp.dataset.param] = inp.value.trim();
    });
    groups.push(g);
  });
  return groups;
}

function _cappAddGroup() {
  const container = document.getElementById("capp-param-groups");
  if (!container || !_cappParamDefs.length) return;
  const groups = _cappCollectGroups();
  const empty = Object.fromEntries(_cappParamDefs.map(p => [p.name, ""]));
  groups.push(empty);
  _cappRenderGroups(groups);
}

function _cappRemoveGroup(idx) {
  const groups = _cappCollectGroups();
  if (groups.length <= 1) return;
  groups.splice(idx, 1);
  _cappRenderGroups(groups);
}

function _cappRenderGroups(groups) {
  const container = document.getElementById("capp-param-groups");
  if (!container) return;
  container.innerHTML = groups.map((g, i) => _paramGroupHtml(_cappParamDefs, g, i, groups.length)).join("");
}

function _cappLog(msg, type, logId) {
  const log = document.getElementById(logId || "capp-run-log");
  if (!log) return;
  log.style.display = "block";
  const ts = new Date().toLocaleTimeString();
  const cls = type === "error" ? "capp-log-error" : type === "done" ? "capp-log-done" : "";
  log.innerHTML += `<div class="capp-log-line ${cls}"><span class="capp-log-ts">${ts}</span>${escapeHtml(msg)}</div>`;
  log.scrollTop = log.scrollHeight;
}

let _cappAbort = null;

async function _readSSE(resp, appId, signal, logId) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      if (signal && signal.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "progress") {
            _cappLog(evt.content, null, logId);
          } else if (evt.type === "done") {
            _cappLog(t("custom.runDone"), "done", logId);
            _showCustomReport({ content: evt.content, date: new Date().toISOString().slice(0,10) });
            if (appId) _refreshCustomReports(appId);
          } else if (evt.type === "error") {
            _cappLog(evt.content || t("custom.runFail"), "error", logId);
          }
        } catch (_) {}
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") throw e;
  } finally {
    try { reader.cancel(); } catch (_) {}
  }
}

function _cappSetRunning(running) {
  const btn = document.getElementById("capp-run-btn");
  if (!btn) return;
  if (running) {
    btn.textContent = `⏹ ${_lang === "zh" ? "停止" : "Stop"}`;
    btn.onclick = () => _cappStopRun();
    btn.disabled = false;
    btn.classList.add("btn-danger");
    btn.classList.remove("btn-primary");
  } else {
    btn.textContent = `🚀 ${t("custom.run")}`;
    const aid = btn.dataset.appId;
    btn.onclick = () => runCustomApp(aid);
    btn.disabled = false;
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-primary");
    _cappAbort = null;
  }
}

function _cappStopRun() {
  if (_cappAbort) { _cappAbort.abort(); _cappAbort = null; }
  _cappLog(_lang === "zh" ? "已终止" : "Stopped", "error");
  _cappSetRunning(false);
}

async function runCustomApp(appId) {
  const log = document.getElementById("capp-run-log");
  if (log) { log.style.display = "block"; log.innerHTML = ""; }

  let capp;
  try { capp = await api(`/api/apps/custom/${appId}`); } catch (_) {}
  if (!capp) { _cappLog("App not found", "error"); return; }

  const paramDefs = capp.parameters || [];
  let paramGroups = paramDefs.length ? _cappCollectGroups() : [{}];
  if (paramDefs.length && !paramGroups.length) {
    paramGroups = [Object.fromEntries(paramDefs.map(p => [p.name, p.default || ""]))];
  }

  for (let gi = 0; gi < paramGroups.length; gi++) {
    const g = paramGroups[gi];
    for (const p of paramDefs) {
      if (!(g[p.name] || "").trim()) {
        const label = `${t("custom.group").replace("{n}", gi + 1)} — ${p.label || p.name}`;
        toast(_lang === "zh" ? `请填写 ${label}` : `Fill in ${label}`, "error");
        const inp = document.querySelector(`.capp-group-input[data-group="${gi}"][data-param="${p.name}"]`);
        if (inp) { inp.focus(); inp.style.borderColor = "var(--red)"; setTimeout(() => inp.style.borderColor = "", 3000); }
        return;
      }
    }
  }

  try { await api(`/api/apps/custom/${appId}`, "PUT", { param_groups: paramGroups }); } catch (_) {}

  _cappSetRunning(true);
  _cappLog(paramGroups.length > 1
    ? (_lang === "zh" ? `开始执行 ${paramGroups.length} 组参数…` : `Running ${paramGroups.length} groups…`)
    : t("custom.running"));
  const ac = new AbortController();
  _cappAbort = ac;

  try {
    const resp = await fetch(`/api/apps/custom/${appId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ param_groups: paramGroups }),
      signal: ac.signal,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      _cappLog(err.error || `HTTP ${resp.status}`, "error");
      _cappSetRunning(false);
      return;
    }
    await _readSSE(resp, appId, ac.signal);
  } catch (e) {
    if (e.name !== "AbortError") _cappLog(e.message, "error");
  } finally {
    _cappSetRunning(false);
    updateUnreadBadges();
  }
}

let _summAbort = null;

async function runCustomSummary(appId) {
  const LOGID = "capp-summ-log";
  const btn = document.getElementById("capp-summ-btn");
  const log = document.getElementById(LOGID);
  if (log) { log.style.display = "block"; log.innerHTML = ""; }

  const ac = new AbortController();
  _summAbort = ac;

  if (btn) {
    btn.textContent = `⏹ ${_lang === "zh" ? "停止" : "Stop"}`;
    btn.onclick = () => { if (_summAbort) { _summAbort.abort(); _summAbort = null; } _cappLog(_lang === "zh" ? "已终止" : "Stopped", "error", LOGID); _summResetBtn(appId); };
    btn.classList.add("btn-danger");
  }

  _cappLog(_lang === "zh" ? "正在调用 LLM 生成总结…" : "Calling LLM for summary…", null, LOGID);

  try {
    const resp = await fetch(`/api/apps/custom/${appId}/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: ac.signal,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      _cappLog(err.error || `HTTP ${resp.status}`, "error", LOGID);
      _summResetBtn(appId);
      return;
    }
    await _readSSE(resp, appId, ac.signal, LOGID);
  } catch (e) {
    if (e.name !== "AbortError") _cappLog(e.message, "error", LOGID);
  } finally {
    _summResetBtn(appId);
    _summAbort = null;
    updateUnreadBadges();
  }
}

function _summResetBtn(appId) {
  const btn = document.getElementById("capp-summ-btn");
  if (!btn) return;
  btn.textContent = `📊 ${t("custom.summaryRun")}`;
  btn.onclick = () => runCustomSummary(appId);
  btn.classList.remove("btn-danger");
}

function _showCustomReport(report) {
  const section = document.getElementById("capp-report-view");
  const content = document.getElementById("capp-report-content");
  const title = document.getElementById("capp-report-view-title");
  if (!section || !content) return;
  title.textContent = `📅 ${report.date || ""}`;
  const raw = report.content || "";
  const rendered = raw.trimStart().startsWith("<") ? raw : renderMarkdown(raw);
  content.innerHTML = rendered;
  if (!raw.trimStart().startsWith("<")) highlightCode(content);
  section.style.display = "block";
  section.scrollIntoView({ behavior: "smooth" });
}

async function viewCustomReport(appId, key) {
  try {
    const report = await api(`/api/apps/custom/${appId}/report/${encodeURIComponent(key)}`);
    if (report.error) { toast(report.error, "error"); return; }
    _showCustomReport(report);
    const dot = document.querySelector(`.capp-report-dot[data-key="${key}"]`);
    if (dot) dot.remove();
    updateUnreadBadges();
  } catch (e) { toast(e.message, "error"); }
}

function _reportItemHtml(appId, r, icon) {
  const dot = r.read ? "" : `<span class="capp-report-dot" data-key="${escapeAttr(r.key)}"></span>`;
  const pu = r.params_used || {};
  const paramLabel = Object.values(pu).filter(v => v).join(", ");
  const paramTag = paramLabel ? `<span class="capp-report-params">${escapeHtml(paramLabel)}</span>` : "";
  return `<div class="digest-report-item" data-report-key="${escapeAttr(r.key)}" onclick="viewCustomReport('${escapeAttr(appId)}','${escapeAttr(r.key)}')">
      ${dot}<span class="digest-report-date">${icon} ${escapeHtml(r.date)}</span>
      ${paramTag}
      <span class="digest-report-time">${escapeHtml(r.generated_at ? r.generated_at.replace("T"," ").slice(0,19) : "")}</span>
      <button class="btn btn-sm">${t("custom.viewReport")}</button>
      <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteCustomReport('${escapeAttr(appId)}','${escapeAttr(r.key)}')" title="${_lang==="zh"?"删除":"Delete"}">🗑</button>
    </div>`;
}

async function deleteCustomReport(appId, key) {
  if (!await showConfirm(_lang === "zh" ? "确定删除此报告？" : "Delete this report?", { danger: true })) return;
  try {
    await api(`/api/apps/custom/${appId}/report/${encodeURIComponent(key)}`, "DELETE");
    const item = document.querySelector(`.digest-report-item[data-report-key="${key}"]`);
    if (item) item.remove();
    updateUnreadBadges();
    toast(_lang === "zh" ? "已删除" : "Deleted", "success");
  } catch (e) { toast(e.message, "error"); }
}

async function _refreshCustomReports(appId) {
  try {
    const reports = await api(`/api/apps/custom/${appId}/reports`);
    const runs = reports.filter(r => (r.type||"run") === "run");
    const list = document.getElementById("capp-report-list");
    if (list) {
      list.innerHTML = runs.length
        ? runs.map(r => _reportItemHtml(appId, r, "📄")).join("")
        : `<div class="digest-empty">${t("custom.noReports")}</div>`;
    }
    const summs = reports.filter(r => r.type === "summary");
    const summList = document.getElementById("capp-summary-list");
    if (summList) {
      summList.innerHTML = summs.length
        ? summs.map(r => _reportItemHtml(appId, r, "📊")).join("")
        : `<div class="digest-empty">${_lang === "zh" ? "暂无总结报告" : "No summaries yet"}</div>`;
    }
  } catch (_) {}
}

// ── Reports Page ──────────────────────────────────────────────────────

let _allReports = [];
let _reportsFilter = "unread";
const _reportsCollapsed = new Set();

async function loadReportsPage() {
  const filtersEl = document.getElementById("reports-filters");
  const contentEl = document.getElementById("reports-content");
  if (!filtersEl || !contentEl) return;

  const filters = [
    { id: "unread", label: t("reports.unread") },
    { id: "24h", label: t("reports.24h") },
    { id: "3d", label: t("reports.3d") },
    { id: "7d", label: t("reports.7d") },
    { id: "30d", label: t("reports.30d") },
    { id: "all", label: t("reports.all") },
  ];
  filtersEl.innerHTML = filters.map(f =>
    `<button class="reports-filter-btn${_reportsFilter === f.id ? ' active' : ''}" data-filter="${f.id}" onclick="setReportsFilter('${f.id}')">${f.label}</button>`
  ).join("");

  contentEl.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;
  try {
    _allReports = await api("/api/reports");
  } catch (_) {
    _allReports = [];
  }
  _renderReports();
}

function setReportsFilter(filter) {
  _reportsFilter = filter;
  document.querySelectorAll(".reports-filter-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.filter === filter);
  });
  _renderReports();
}

function _renderReports() {
  const contentEl = document.getElementById("reports-content");
  if (!contentEl) return;

  const now = Date.now();
  const filtered = _allReports.filter(r => {
    const ts = new Date(r.generated_at || r.date).getTime();
    switch (_reportsFilter) {
      case "unread": return !r.read;
      case "24h": return now - ts < 86400000;
      case "3d": return now - ts < 259200000;
      case "7d": return now - ts < 604800000;
      case "30d": return now - ts < 2592000000;
      default: return true;
    }
  });

  let topBar = `<div class="reports-top-bar">`;
  topBar += `<button class="btn btn-sm reports-mark-all-read" onclick="markAllReportsRead()">✓ ${t("reports.markAllRead")}</button>`;
  topBar += `</div>`;

  if (!filtered.length) {
    const hint = _reportsFilter === "unread" ? t("reports.allRead") : t("reports.empty");
    contentEl.innerHTML = `${topBar}<div class="digest-empty">${hint}</div>`;
    return;
  }

  const groups = {};
  for (const r of filtered) {
    const gKey = r.app_id;
    if (!groups[gKey]) groups[gKey] = { name: r.app_name, icon: r.app_icon, items: [] };
    groups[gKey].items.push(r);
  }

  let html = topBar;
  for (const [appId, group] of Object.entries(groups)) {
    const unreadCount = group.items.filter(r => !r.read).length;
    const unreadBadge = unreadCount > 0 ? `<span class="reports-group-badge">${unreadCount}</span>` : "";
    const collapsed = _reportsCollapsed.has(appId);
    html += `<div class="reports-group${collapsed ? ' collapsed' : ''}">
      <div class="reports-group-header" onclick="toggleReportsGroup('${escapeAttr(appId)}')">
        <span class="reports-group-arrow">${collapsed ? '▶' : '▼'}</span>
        ${group.icon} ${escapeHtml(group.name)} ${unreadBadge}
      </div>
      <div class="reports-group-list"${collapsed ? ' style="display:none"' : ''}>`;

    for (const r of group.items) {
      const time = (r.generated_at || "").replace("T", " ").slice(0, 16);
      const unreadDot = r.read ? "" : `<span class="reports-unread-dot"></span>`;
      const summary = r.summary ? `<span class="reports-item-summary">${escapeHtml(r.summary)}</span>` : "";
      html += `<div class="reports-item${r.read ? '' : ' unread'}">
        ${unreadDot}
        <span class="reports-item-date" onclick="openReportInline('${escapeAttr(appId)}','${escapeAttr(r.key)}')">${escapeHtml(r.date)}</span>
        <span class="reports-item-summary-wrap" onclick="openReportInline('${escapeAttr(appId)}','${escapeAttr(r.key)}')">${summary}</span>
        <span class="reports-item-time">${escapeHtml(time)}</span>
        <button class="btn btn-sm" onclick="openReportInline('${escapeAttr(appId)}','${escapeAttr(r.key)}')">${t("reports.viewReport")}</button>
        <button class="btn btn-sm reports-item-delete" onclick="event.stopPropagation();deleteReport('${escapeAttr(appId)}','${escapeAttr(r.key)}')" title="${t("reports.delete")}">🗑</button>
      </div>`;
    }
    html += `</div></div>`;
  }
  contentEl.innerHTML = html;
}

async function openReportInline(appId, key) {
  const filtersEl = document.getElementById("reports-filters");
  const contentEl = document.getElementById("reports-content");
  if (!contentEl) return;

  if (filtersEl) filtersEl.style.display = "none";
  contentEl.classList.add("viewing-report");
  contentEl.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  try {
    const report = await api(`/api/reports/${encodeURIComponent(appId)}/${encodeURIComponent(key)}`);
    if (report.error) { toast(report.error, "error"); _closeReportInline(); return; }

    const r = _allReports.find(x => x.app_id === appId && x.key === key);
    const reportTitle = report.title || (r ? `${r.app_icon || ''} ${r.app_name || ''} — ${r.date}` : key);

    const raw = report.content || "";
    const htmlContent = raw.trimStart().startsWith("<") ? raw : (typeof renderMarkdown === "function" ? renderMarkdown(raw) : `<pre>${escapeHtml(raw)}</pre>`);

    contentEl.innerHTML = `<div class="report-inline-viewer">
      <div class="report-inline-header">
        <button class="btn btn-sm" onclick="_closeReportInline()">\u2190 ${t("apps.back")}</button>
        <h2>${escapeHtml(reportTitle)}</h2>
      </div>
      <div class="report-inline-body">
        <div class="report-inline-content digest-report-content">${htmlContent}</div>
      </div>
    </div>`;

    _injectExploreButtonsForInline(contentEl, report, appId);

    if (r) r.read = true;
    updateUnreadBadges();
  } catch (e) {
    toast(e.message, "error");
    _closeReportInline();
  }
}

function _injectExploreButtonsForInline(container, report, appId) {
  if (appId !== "daily_digest") return;
  const wrapper = container.querySelector(".report-inline-content");
  if (wrapper) _injectExploreButtons(wrapper, report);
}

function _closeReportInline() {
  const filtersEl = document.getElementById("reports-filters");
  const contentEl = document.getElementById("reports-content");
  if (filtersEl) filtersEl.style.display = "";
  if (contentEl) contentEl.classList.remove("viewing-report");
  _renderReports();
}

function toggleReportsGroup(appId) {
  if (_reportsCollapsed.has(appId)) _reportsCollapsed.delete(appId);
  else _reportsCollapsed.add(appId);
  _renderReports();
}

async function markAllReportsRead() {
  try {
    await api("/api/reports/mark_all_read", "POST");
    _allReports.forEach(r => { r.read = true; });
    _renderReports();
    updateUnreadBadges();
  } catch (e) { toast(e.message, "error"); }
}

async function deleteReport(appId, key) {
  try {
    const res = await api(`/api/reports/${encodeURIComponent(appId)}/${encodeURIComponent(key)}`, "DELETE");
    if (res.error) { toast(t("reports.deleteFail"), "error"); return; }
    _allReports = _allReports.filter(r => !(r.app_id === appId && r.key === key));
    toast(t("reports.deleteOk"), "ok");
    _renderReports();
    updateUnreadBadges();
  } catch (e) { toast(t("reports.deleteFail"), "error"); }
}

// ── Unread badges ─────────────────────────────────────────────────────

let _unreadCounts = {};

async function updateUnreadBadges() {
  let total = 0;
  try {
    const data = await api("/api/reports/unread_count");
    total = data.total || 0;
  } catch (_) {}
  try { _unreadCounts = await api("/api/apps/custom/unread"); } catch (_) { _unreadCounts = {}; }
  let navBadge = document.getElementById("nav-reports-badge");
  if (!navBadge) {
    const navItem = document.querySelector('.nav-item[data-page="reports"]');
    if (navItem) {
      navBadge = document.createElement("span");
      navBadge.id = "nav-reports-badge";
      navBadge.className = "nav-badge";
      navItem.appendChild(navBadge);
    }
  }
  if (navBadge) {
    navBadge.textContent = total > 0 ? total : "";
    navBadge.style.display = total > 0 ? "" : "none";
  }
}

function _appCardBadge(appId) {
  return "";
}

let _badgePollTimer = null;
function _startBadgePoll() {
  if (_badgePollTimer) return;
  _badgePollTimer = setInterval(() => { updateUnreadBadges(); updateSidebarStats(); }, 30000);
  _startTaskPanelPoll();
}

async function updateSidebarStats() {
  const tokEl = document.getElementById("stat-tokens");
  const searchEl = document.getElementById("stat-search");
  if (!tokEl || !searchEl) return;
  try {
    const [tok, search] = await Promise.all([
      api("/api/token/usage").catch(() => null),
      api("/api/search/usage").catch(() => null),
    ]);
    if (tok) {
      const inp = tok.input_tokens || 0;
      const out = tok.output_tokens || 0;
      tokEl.textContent = `${t("stats.todayPrefix")} ↓${_fmtNum(inp)} ↑${_fmtNum(out)}`;
      tokEl.title = t("stats.tokenTip");
    }
    if (search && search.engines) {
      const parts = [];
      for (const [eng, v] of Object.entries(search.engines)) {
        if (!v.has_key) continue;
        const label = eng.charAt(0).toUpperCase() + eng.slice(1);
        parts.push(`${label} ${v.used || 0}/${v.limit || 1000}`);
      }
      searchEl.textContent = parts.length ? parts.join("  ") : "";
      searchEl.title = parts.length ? t("stats.searchTip") : "";
      const sep = document.getElementById("stat-sep");
      if (sep) sep.style.display = parts.length ? "" : "none";
    }
  } catch (_) {}
}

// ── Task Panel (floating popover) ─────────────────────────────────
let _taskPollTimer = null;
let _taskPollFast = false;
let _lastTasksJson = "";
let _taskPanelOpen = false;
let _cachedTasks = [];

function _startTaskPanelPoll() {
  if (_taskPollTimer) return;
  _fetchTasks();
  _taskPollTimer = setInterval(_fetchTasks, 15000);
}

function _setTaskPollSpeed(fast) {
  if (fast === _taskPollFast) return;
  _taskPollFast = fast;
  if (_taskPollTimer) clearInterval(_taskPollTimer);
  _taskPollTimer = setInterval(_fetchTasks, fast ? 5000 : 15000);
}

async function _fetchTasks() {
  try {
    const data = await api("/api/scheduler/today");
    if (!data || !data.tasks) return;
    const tasks = data.tasks;
    const json = JSON.stringify(tasks);
    if (json === _lastTasksJson) return;
    _lastTasksJson = json;
    _cachedTasks = tasks;
    _updateTaskBadge(tasks);
    if (_taskPanelOpen) _renderTaskPanel(tasks);
    const hasActive = tasks.some(t => t.status === "running" || t.status === "pending_catchup");
    _setTaskPollSpeed(hasActive);
  } catch (_) {}
}

function _updateTaskBadge(tasks) {
  const badge = document.getElementById("task-badge");
  const btn = document.getElementById("task-nav-btn");
  if (!badge) return;
  const running = tasks.filter(t => t.status === "running").length;
  if (running > 0) {
    badge.setAttribute("data-count", String(running));
    badge.setAttribute("data-has-running", "true");
    badge.textContent = String(running);
    badge.style.display = "";
    if (btn) btn.classList.add("has-active");
  } else {
    badge.removeAttribute("data-count");
    badge.removeAttribute("data-has-running");
    badge.style.display = "none";
    if (btn) btn.classList.remove("has-active");
  }
}

function toggleTaskPanel() {
  const panel = document.getElementById("task-panel");
  if (!panel) return;
  _taskPanelOpen = !_taskPanelOpen;
  panel.style.display = _taskPanelOpen ? "" : "none";
  if (_taskPanelOpen) {
    _fetchTasks();
    _renderTaskPanel(_cachedTasks);
  }
}

function _renderTaskPanel(tasks) {
  const body = document.getElementById("task-panel-body");
  const countEl = document.getElementById("task-panel-count");
  if (!body) return;

  if (!tasks || tasks.length === 0) {
    body.innerHTML = `<div class="task-panel-empty">${t("tasks.noTasks")}</div>`;
    if (countEl) countEl.textContent = "";
    return;
  }

  const done = tasks.filter(t => t.status === "success").length;
  if (countEl) countEl.textContent = `${done}/${tasks.length}`;

  let html = "";
  for (const task of tasks) {
    const statusLabel = _taskStatusLabel(task.status);
    const timeStr = _taskTimeDisplay(task);
    const tName = (_lang === "en" ? task.name_en : task.name_zh) || task.name_zh || task.task_id;
    const canRun = task.status === "planned" || task.status === "failed" || task.status === "pending_catchup";
    const runBtn = canRun
      ? `<button class="task-run-btn" onclick="triggerTask('${_escAttr(task.task_id)}')" title="${t("tasks.runNow")}">▶</button>`
      : task.status === "running"
        ? `<span class="task-running-indicator">⏳</span>`
        : "";
    html += `<div class="task-item" title="${_escAttr(tName)}">
      <span class="task-item-icon">${task.icon || "🤖"}</span>
      <div class="task-item-body">
        <span class="task-item-name">${_escHtml(tName)}</span>
        <div class="task-item-meta">
          <span class="task-item-dot" data-status="${task.status}"></span>
          <span class="task-item-status-text" data-status="${task.status}">${statusLabel}</span>
          <span>${timeStr}</span>
        </div>
      </div>
      ${runBtn}
    </div>`;
  }
  body.innerHTML = html;
}

async function triggerTask(taskId) {
  const btn = document.querySelector(`.task-run-btn[onclick*="${taskId}"]`);
  if (btn) { btn.disabled = true; btn.textContent = "⏳"; }
  try {
    const res = await api(`/api/scheduler/trigger/${encodeURIComponent(taskId)}`, "POST");
    if (res.success) {
      toast(t("tasks.triggered") || "已触发执行", "success");
      _setTaskPollSpeed(true);
      setTimeout(_fetchTasks, 1000);
    } else {
      toast(res.error || t("tasks.triggerFail"), "error");
      if (btn) { btn.disabled = false; btn.textContent = "▶"; }
    }
  } catch (e) {
    toast(e.message, "error");
    if (btn) { btn.disabled = false; btn.textContent = "▶"; }
  }
}

function _taskStatusLabel(status) {
  const map = {
    planned: t("tasks.planned"),
    pending_catchup: t("tasks.pendingCatchup"),
    running: t("tasks.running"),
    success: t("tasks.success"),
    failed: t("tasks.failed"),
  };
  return map[status] || status;
}

function _taskTimeDisplay(task) {
  if (task.status === "success" && task.finished_at) {
    try {
      const d = new Date(task.finished_at);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      let label = `${hh}:${mm} ✓`;
      if (task.trigger === "startup" || task.trigger === "resume") {
        label += ` (${t("tasks.catchupNote")})`;
      }
      return label;
    } catch (_) {}
  }
  if (task.status === "running") {
    return task.scheduled_time ? `${task.scheduled_time} →` : "→";
  }
  if (task.status === "failed") {
    return task.scheduled_time || "";
  }
  if (task.status === "pending_catchup") {
    return task.scheduled_time ? `${task.scheduled_time} ⏎` : "⏎";
  }
  return task.scheduled_time || "";
}

function _escHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function _escAttr(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;"); }

function updateTaskPanel() { _fetchTasks(); }

document.addEventListener("click", (e) => {
  if (!_taskPanelOpen) return;
  const panel = document.getElementById("task-panel");
  const btn = document.getElementById("task-nav-btn");
  if (panel && !panel.contains(e.target) && btn && !btn.contains(e.target)) {
    _taskPanelOpen = false;
    panel.style.display = "none";
  }
});

async function openCustomAppWizardEdit(appId) {
  let capp;
  try { capp = await api(`/api/apps/custom/${appId}`); } catch (_) {}
  if (!capp || capp.error) { toast("App not found", "error"); return; }
  openCustomAppWizard(null, null, capp);
}

// ── Security Mode ────────────────────────────────────────────────
let currentSecurityMode = "Assistant";

async function loadSecurityMode() {
  try {
    const data = await api("/api/security/mode");
    if (data && data.mode) {
      currentSecurityMode = data.mode;
      const sel = document.getElementById("security-mode-select");
      if (sel) {
        if (data.mode === "Developer") {
          _ensureDevOption(sel);
        }
        sel.value = data.mode;
      }
      updateSecurityModeHint(data.mode);
    }
    _updateDevModeIndicator();
  } catch (_) {}
}

function _ensureDevOption(sel) {
  if (!sel.querySelector('option[value="Developer"]')) {
    const opt = document.createElement("option");
    opt.value = "Developer";
    opt.dataset.i18n = "security.opt.Developer";
    opt.textContent = t("security.opt.Developer");
    sel.appendChild(opt);
  }
}

async function switchSecurityMode(mode) {
  if (mode === "Developer") {
    toast(t("security.devRequired"), "error");
    const sel = document.getElementById("security-mode-select");
    if (sel) sel.value = currentSecurityMode;
    return;
  }
  try {
    const data = await api("/api/security/mode", "POST", { mode });
    if (data && data.mode) {
      currentSecurityMode = data.mode;
      updateSecurityModeHint(data.mode);
      toast(`${t("security.switched")} ${_modeName(data.mode)}`, "success");
    } else if (data && data.error) {
      toast(data.error, "error");
      const sel = document.getElementById("security-mode-select");
      if (sel) sel.value = currentSecurityMode;
    } else {
      toast(t("security.switchFail"), "error");
    }
  } catch (e) {
    toast(`${t("security.switchFail")}: ${e}`, "error");
    const sel = document.getElementById("security-mode-select");
    if (sel) sel.value = currentSecurityMode;
  }
}

function updateSecurityModeHint(mode) {
  const hint = document.getElementById("security-mode-hint");
  if (hint) hint.textContent = t(`security.${mode}`) || "";
  const bar = document.getElementById("security-mode-bar");
  if (bar) {
    bar.className = "security-mode-bar security-mode-" + mode.toLowerCase();
  }
}

async function _updateDevModeIndicator() {
  const indicator = document.getElementById("dev-mode-indicator");
  if (!indicator) return;
  try {
    const data = await api("/api/security/dev/status");
    if (data.enabled && !data.is_expired) {
      indicator.style.display = "inline-flex";
      const remaining = data.remaining_seconds;
      if (remaining !== null && remaining !== undefined) {
        const mins = Math.ceil(remaining / 60);
        indicator.textContent = `🔓 ${_modeName("Developer")} (${mins}m)`;
        indicator.className = "dev-mode-indicator dev-active";
      } else {
        indicator.textContent = `🔓 ${_modeName("Developer")}`;
        indicator.className = "dev-mode-indicator dev-active";
      }
    } else {
      indicator.style.display = "none";
    }
  } catch (_) {
    indicator.style.display = "none";
  }
}

async function openDevModeSettings() {
  let status;
  try { status = await api("/api/security/dev/status"); } catch (_) { status = {}; }

  const isActive = status.enabled && !status.is_expired;
  const remaining = status.remaining_seconds;
  const policy = status.expiry_policy || "on_app_close";

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  if (isActive) {
    const remStr = remaining !== null && remaining !== undefined
      ? `${Math.ceil(remaining / 60)} ${t("security.devUnit.min")}`
      : t("security.devExpiry.on_app_close");
    modal.innerHTML = `
      <div class="modal-card" style="max-width:400px;">
        <h3 style="margin:0 0 12px;">🔓 ${t("security.devActive")}</h3>
        <div style="margin-bottom:8px;">
          <strong>${t("security.devExpiry")}:</strong> ${t("security.devExpiry." + policy)}
        </div>
        <div style="margin-bottom:16px;">
          <strong>${t("security.devRemaining")}:</strong> ${remStr}
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;">
          <button class="btn" onclick="this.closest('.modal-overlay').remove()">${t("security.devClose")}</button>
          <button class="btn btn-danger" onclick="_disableDevMode(this)">${t("security.devDisable")}</button>
        </div>
      </div>
    `;
  } else {
    modal.innerHTML = `
      <div class="modal-card" style="max-width:420px;">
        <h3 style="margin:0 0 12px;">⚙️ ${t("security.devEnable")}</h3>
        <div style="margin-bottom:8px;color:var(--text-danger,#dc3545);">
          ⚠️ ${t("security.devCard.warning")}
        </div>
        <div class="form-group" style="margin:12px 0;">
          <label>${t("security.devExpiry")}</label>
          <select id="dev-expiry-select" class="digest-select">
            <option value="on_app_close">${t("security.devExpiry.on_app_close")}</option>
            <option value="duration_1h">${t("security.devExpiry.duration_1h")}</option>
            <option value="duration_24h">${t("security.devExpiry.duration_24h")}</option>
          </select>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;">
          <button class="btn" onclick="this.closest('.modal-overlay').remove()">${t("custom.escalation.cancel")}</button>
          <button class="btn btn-danger" onclick="_enableDevMode(this)">${t("security.devEnable")}</button>
        </div>
      </div>
    `;
  }
  document.body.appendChild(modal);
}

async function _enableDevMode(btn) {
  const modal = btn.closest(".modal-overlay");
  const sel = modal.querySelector("#dev-expiry-select");
  const policy = sel ? sel.value : "on_app_close";
  btn.disabled = true;
  try {
    const res = await api("/api/security/dev/enable", "POST", { expiry_policy: policy });
    if (res.success) {
      toast(t("security.devActive"), "success");
      modal.remove();
      const globalSel = document.getElementById("security-mode-select");
      if (globalSel) {
        _ensureDevOption(globalSel);
        globalSel.value = "Developer";
      }
      await api("/api/security/mode", "POST", { mode: "Developer" });
      currentSecurityMode = "Developer";
      updateSecurityModeHint("Developer");
      _updateDevModeIndicator();
    } else {
      toast(res.error || t("security.switchFail"), "error");
      btn.disabled = false;
    }
  } catch (e) {
    toast(e.message, "error");
    btn.disabled = false;
  }
}

async function _disableDevMode(btn) {
  btn.disabled = true;
  try {
    const res = await api("/api/security/dev/disable", "POST");
    if (res.success) {
      toast(t("security.devDisabled"), "info");
      btn.closest(".modal-overlay").remove();
      currentSecurityMode = res.reverted_to || "Operator";
      const sel = document.getElementById("security-mode-select");
      if (sel) {
        const devOpt = sel.querySelector('option[value="Developer"]');
        if (devOpt) devOpt.remove();
        sel.value = currentSecurityMode;
      }
      updateSecurityModeHint(currentSecurityMode);
      _updateDevModeIndicator();
    }
  } catch (e) {
    toast(e.message, "error");
    btn.disabled = false;
  }
}

// Load security mode on startup
document.addEventListener("DOMContentLoaded", () => { loadSecurityMode(); });

// ── Plan Confirmation ────────────────────────────────────────────

let _pendingPollTimer = null;

function startPendingPoll() {
  // Confirmation is now handled inline in the chat conversation.
  // No modal polling needed.
}

function stopPendingPoll() {
  if (_pendingPollTimer) { clearInterval(_pendingPollTimer); _pendingPollTimer = null; }
}

async function checkPendingActions() {
  // No-op: confirmation handled via chat.
}

function showPlanConfirmModal(action) {
  const modal = document.getElementById("plan-confirm-modal");
  if (!modal) return;

  const riskBadge = document.getElementById("plan-risk-badge");
  const explainEl = document.getElementById("plan-explain");
  const detailEl = document.getElementById("plan-detail");
  const evidenceEl = document.getElementById("plan-evidence");

  const risk = action.risk || 0;
  let riskClass = "plan-risk-low";
  let riskLabel = "Low Risk";
  if (risk > 70) { riskClass = "plan-risk-critical"; riskLabel = "Critical Risk"; }
  else if (risk > 50) { riskClass = "plan-risk-high"; riskLabel = "High Risk"; }
  else if (risk > 30) { riskClass = "plan-risk-medium"; riskLabel = "Medium Risk"; }

  riskBadge.className = "plan-risk-badge " + riskClass;
  riskBadge.textContent = `${riskLabel} (${risk}/100)`;
  explainEl.textContent = action.explain || "";
  detailEl.textContent = `${action.tool_name}(${JSON.stringify(action.tool_args || {}).substring(0, 200)})`;

  const ev = action.evidence || {};
  evidenceEl.innerHTML = [
    ev.mode ? `Mode: ${ev.mode}` : "",
    ev.capability ? `Capability: ${ev.capability}.${ev.op || ""}` : "",
    ev.matched_rule ? `Rule: ${ev.matched_rule}` : "",
  ].filter(Boolean).map(s => `<div>${s}</div>`).join("");

  const confirmBtn = document.getElementById("plan-confirm-btn");
  const rejectBtn = document.getElementById("plan-reject-btn");
  confirmBtn.onclick = () => confirmPendingAction(action.action_id);
  rejectBtn.onclick = () => rejectPendingAction(action.action_id);

  modal.style.display = "flex";
}

function closePlanConfirmModal() {
  const modal = document.getElementById("plan-confirm-modal");
  if (modal) modal.style.display = "none";
}

async function confirmPendingAction(actionId) {
  closePlanConfirmModal();
  try {
    const result = await api(`/api/plan/confirm/${actionId}`, "POST");
    if (result.success) {
      toast(t("plan.confirmed") || "操作已确认并执行", "success");
      if (result.cooldown_seconds) {
        showCooldownToast(actionId, result.cooldown_seconds, result.capability || "");
      }
    } else {
      toast(`${t("plan.confirmFail") || "执行失败"}: ${result.error}`, "error");
    }
  } catch (e) {
    toast(`Error: ${e}`, "error");
  }
}

async function rejectPendingAction(actionId) {
  closePlanConfirmModal();
  try {
    await api(`/api/plan/reject/${actionId}`, "POST");
    toast(t("plan.rejected") || "操作已拒绝", "info");
  } catch (e) {
    toast(`Error: ${e}`, "error");
  }
}

// Start polling when chat page is active
document.addEventListener("DOMContentLoaded", () => { startPendingPoll(); });

// ── Cooldown Toast ───────────────────────────────────────────────

function showCooldownToast(actionId, seconds, capability) {
  const container = document.getElementById("cooldown-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "cooldown-toast";
  toast.id = `cooldown-${actionId}`;

  let remaining = seconds;
  toast.innerHTML = `
    <div class="cooldown-timer" id="cd-timer-${actionId}">${remaining}</div>
    <div class="cooldown-info">
      <div class="cooldown-action">${capability || "操作"}</div>
      <div style="color:var(--text-dim);font-size:0.8rem">冷静期内可撤销</div>
    </div>
    <button class="btn-cooldown-undo" onclick="cooldownUndo('${actionId}')">撤销</button>
  `;
  container.appendChild(toast);

  const timerEl = document.getElementById(`cd-timer-${actionId}`);
  const interval = setInterval(() => {
    remaining--;
    if (timerEl) timerEl.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(interval);
      toast.remove();
    }
  }, 1000);
}

async function cooldownUndo(actionId) {
  const el = document.getElementById(`cooldown-${actionId}`);
  try {
    const result = await api(`/api/undo/${actionId}`, "POST");
    if (result.success) {
      toast(t("audit.undoSuccess") || "撤销成功", "success");
    } else {
      toast(`${t("audit.undoFail") || "撤销失败"}: ${result.error}`, "error");
    }
  } catch (e) {
    toast(`Error: ${e}`, "error");
  }
  if (el) el.remove();
}

// ── Audit & Undo ─────────────────────────────────────────────────

async function loadAuditPage() {
  const listEl = document.getElementById("audit-list");
  const undoEl = document.getElementById("undo-list");
  if (!listEl) return;

  try {
    const [entries, actions] = await Promise.all([
      api("/api/audit/recent?n=50"),
      api("/api/undo/actions?undoable=true"),
    ]);

    if (!entries || entries.length === 0) {
      listEl.innerHTML = `<div class="empty-hint">${t("audit.empty")}</div>`;
    } else {
      listEl.innerHTML = entries.map(e => `
        <div class="audit-entry">
          <div class="audit-entry-header">
            <span class="audit-cap">${e.capability || ""}</span>
            <span class="audit-mode">${e.mode || ""}</span>
            <span class="audit-ts">${e.ts ? new Date(e.ts).toLocaleString() : ""}</span>
          </div>
          <div class="audit-entry-detail">
            <span class="audit-risk">risk: ${e.decision?.risk ?? "?"}</span>
            <span class="audit-hash" title="${e.entry_hash || ""}">#${(e.entry_hash || "").slice(0, 8)}</span>
          </div>
        </div>
      `).join("");
    }

    if (!actions || actions.length === 0) {
      undoEl.innerHTML = `<div class="empty-hint">${t("audit.noUndo")}</div>`;
    } else {
      const now = Date.now() / 1000;
      undoEl.innerHTML = actions.map(a => {
        const inCooldown = a.cooldown_until && a.cooldown_until > now;
        const cooldownLeft = inCooldown ? Math.ceil(a.cooldown_until - now) : 0;
        return `
          <div class="undo-entry${inCooldown ? " undo-cooldown" : ""}">
            <div class="undo-info">
              <span class="undo-cap">${a.capability}.${a.op}</span>
              <span class="undo-ts">${new Date(a.ts * 1000).toLocaleString()}</span>
              ${inCooldown ? `<span class="cooldown-badge">冷静期 ${cooldownLeft}s</span>` : ""}
            </div>
            <button class="btn-undo" onclick="undoAction('${a.action_id}')"${a.undone ? " disabled" : ""}>
              ${a.undone ? "已撤销" : "撤销"}
            </button>
          </div>`;
      }).join("");
    }
  } catch (e) {
    listEl.innerHTML = `<div class="empty-hint">Error: ${e}</div>`;
  }
}

async function verifyAuditChain() {
  const statusEl = document.getElementById("audit-chain-status");
  try {
    const result = await api("/api/audit/verify");
    if (result.valid) {
      statusEl.innerHTML = `<div class="audit-valid">${t("audit.chainValid")} (${result.entries_checked} entries)</div>`;
    } else {
      statusEl.innerHTML = `<div class="audit-invalid">${t("audit.chainInvalid")}: ${result.error}</div>`;
    }
  } catch (e) {
    statusEl.innerHTML = `<div class="audit-invalid">Error: ${e}</div>`;
  }
}

async function exportAuditChain() {
  try {
    const resp = await fetch("/api/audit/export");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit_chain.json";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    toast(`Export failed: ${e}`, "error");
  }
}

async function undoAction(actionId) {
  try {
    const result = await api(`/api/undo/${actionId}`, "POST");
    if (result.success) {
      toast(t("audit.undoSuccess"), "success");
      loadAuditPage();
    } else {
      toast(`${t("audit.undoFail")}: ${result.error}`, "error");
    }
  } catch (e) {
    toast(`${t("audit.undoFail")}: ${e}`, "error");
  }
}

// ── Privacy & Personalization ────────────────────────────────────

async function loadPrivacySettings() {
  try {
    const data = await api("/api/profile/collection");
    if (data) {
      const br = document.getElementById("privacy-browser");
      const ch = document.getElementById("privacy-chat");
      const fi = document.getElementById("privacy-file");
      const ad = document.getElementById("privacy-analysis-days");
      const paths = document.getElementById("privacy-watch-paths");
      const pd = document.getElementById("privacy-persona-digest");
      if (br) br.checked = data.browser_history !== false;
      if (ch) ch.checked = data.chat_history !== false;
      if (fi) fi.checked = !!data.file_history;
      if (ad) ad.value = data.analysis_days || 7;
      if (paths && data.watch_paths) paths.value = (data.watch_paths || []).join("\n");
      if (pd) pd.checked = !!data.persona_in_digest;
      toggleFileWatchPaths();
    }
  } catch (_) {}
  updatePersonaStatusBanner();
  loadPersonaEffect();
}

function toggleFileWatchPaths() {
  const fi = document.getElementById("privacy-file");
  const item = document.getElementById("file-watch-paths-item");
  if (item) item.style.display = fi?.checked ? "" : "none";
}

function updatePersonaStatusBanner() {
  const br = document.getElementById("privacy-browser")?.checked;
  const ch = document.getElementById("privacy-chat")?.checked;
  const fi = document.getElementById("privacy-file")?.checked;
  const banner = document.getElementById("persona-status-banner");
  const text = document.getElementById("persona-status-text");
  if (!banner || !text) return;

  const anyOn = br || ch || fi;
  if (!anyOn) {
    banner.style.display = "";
    text.textContent = t("privacy.statusOff");
    banner.style.borderLeftColor = "var(--yellow)";
  } else {
    banner.style.display = "";
    text.textContent = t("privacy.statusOn");
    banner.style.borderLeftColor = "var(--green)";
  }
}

async function savePrivacySettings() {
  const pathsText = document.getElementById("privacy-watch-paths")?.value || "";
  const watchPaths = pathsText.split("\n").map(p => p.trim()).filter(p => p.length > 0);
  const settings = {
    browser_history: document.getElementById("privacy-browser")?.checked ?? true,
    chat_history: document.getElementById("privacy-chat")?.checked ?? true,
    file_history: document.getElementById("privacy-file")?.checked ?? false,
    watch_paths: watchPaths,
    analysis_days: parseInt(document.getElementById("privacy-analysis-days")?.value || "7", 10),
    persona_in_digest: document.getElementById("privacy-persona-digest")?.checked ?? false,
  };
  try {
    await api("/api/profile/collection", "POST", settings);
    toast(t("privacy.saved"), "success");
  } catch (e) {
    toast(`Error: ${e}`, "error");
  }
  updatePersonaStatusBanner();
}

async function generatePersona() {
  const btn = event?.target;
  if (btn) {
    btn.disabled = true;
    btn.textContent = t("privacy.generating");
  }
  try {
    await api("/api/profile/persona/update", "POST");
    toast(t("privacy.generated"), "success");
    loadPersonaEffect();
  } catch (e) {
    toast(`Error: ${e}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = t("privacy.generate");
    }
  }
}

async function loadPersonaEffect() {
  const section = document.getElementById("persona-effect-section");
  const styleText = document.getElementById("persona-style-text");
  const directionText = document.getElementById("persona-direction-text");
  if (!section) return;

  try {
    const persona = await api("/api/profile/persona");
    if (!persona || !persona.has_data) {
      section.style.display = "none";
      return;
    }

    const zh = _lang === "zh";
    const stable = persona.stable || {};
    const recent = persona.recent || {};

    if (styleText) {
      styleText.textContent = stable.prompt_text
        || (zh ? "暂无稳定画像，点击「生成个性化」开始。" : "No stable profile yet. Click 'Generate' to start.");
    }

    if (directionText) {
      directionText.textContent = recent.prompt_text
        || (zh ? "暂无近期兴趣数据，点击「生成个性化」开始。" : "No recent data yet. Click 'Generate' to start.");
    }

    section.style.display = "";
  } catch (_) {
    section.style.display = "none";
  }
}

function copyPersonaBlock(which) {
  let text = "";
  if (which === "style") {
    text = document.getElementById("persona-style-text")?.textContent || "";
  } else if (which === "direction") {
    text = document.getElementById("persona-direction-text")?.textContent || "";
  }
  if (text) {
    navigator.clipboard.writeText(text).then(() => {
      toast(t("privacy.copied"), "success");
    });
  }
}

function editPersonaBlock(part) {
  const cardId = part === "stable" ? "persona-effect-style" : "persona-effect-direction";
  const textId = part === "stable" ? "persona-style-text" : "persona-direction-text";
  const card = document.getElementById(cardId);
  const textEl = document.getElementById(textId);
  if (!card || !textEl) return;

  if (card.querySelector(".persona-edit-textarea")) return;

  const current = textEl.textContent;
  textEl.style.display = "none";

  const textarea = document.createElement("textarea");
  textarea.className = "persona-edit-textarea";
  textarea.value = current;
  card.appendChild(textarea);

  const actions = document.createElement("div");
  actions.className = "persona-edit-actions";
  actions.innerHTML = `<button class="btn-secondary" data-action="cancel">${_lang === "zh" ? "取消" : "Cancel"}</button>
    <button class="btn btn-primary" data-action="save">${_lang === "zh" ? "保存" : "Save"}</button>`;
  card.appendChild(actions);

  textarea.focus();

  actions.addEventListener("click", async (e) => {
    const action = e.target.dataset?.action;
    if (action === "cancel") {
      textarea.remove();
      actions.remove();
      textEl.style.display = "";
    } else if (action === "save") {
      const newVal = textarea.value.trim();
      try {
        await api(`/api/profile/persona/edit/${part}`, "POST", { prompt_text: newVal });
        toast(t("privacy.editSaved"), "success");
        textEl.textContent = newVal;
      } catch (err) {
        toast(`Error: ${err}`, "error");
      }
      textarea.remove();
      actions.remove();
      textEl.style.display = "";
    }
  });
}

async function clearProfile() {
  const zh = _lang === "zh";
  if (!confirm(zh ? "确定要清空所有个性化数据？" : "Clear all personalization data?")) return;
  try {
    await api("/api/profile/clear", "POST");
    toast(t("privacy.cleared"), "success");
    const section = document.getElementById("persona-effect-section");
    if (section) section.style.display = "none";
  } catch (e) {
    toast(`Clear failed: ${e}`, "error");
  }
}

// Load privacy settings when opening settings page
const _origLoadConfig = typeof loadConfig === "function" ? loadConfig : null;
if (_origLoadConfig) {
  const _wrappedLoadConfig = loadConfig;
  loadConfig = function() {
    _wrappedLoadConfig.apply(this, arguments);
    loadPrivacySettings();
  };
}

