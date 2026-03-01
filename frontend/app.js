/* ===================================================================
   Otta — Frontend Logic
   =================================================================== */

// Build version probe — server injects __myxai_expected_build in <head>.
// Used to detect stale pages (e.g. old browser tab left open).
window.__myxai_build__ = window.__myxai_expected_build || "";

// ── API token guard (localhost CSRF / DNS-rebinding protection) ────
// Priority: inline <script> injection (most reliable) > URL param (dev) > sessionStorage (refresh fallback)
(function _bootstrapToken() {
  if (!window.__myxai_token) {
    const p = new URLSearchParams(window.location.search);
    const t = p.get("token");
    if (t) {
      window.__myxai_token = t;
      const clean = window.location.pathname + window.location.hash;
      window.history.replaceState(null, "", clean);
    }
  }
  if (!window.__myxai_token) {
    window.__myxai_token = sessionStorage.getItem("__myxai_token") || "";
  }
  if (window.__myxai_token) {
    sessionStorage.setItem("__myxai_token", window.__myxai_token);
  }
})();

// ── Stale page detection — stop polls and show banner if version mismatches ──
(function _checkStalePage() {
  var expected = window.__myxai_expected_build || "";
  var actual = window.__myxai_build__ || "";
  if (expected && actual === expected) return;
  if (!expected && !actual) return;
  console.warn("[MyxAI] Stale page detected (expected=" + expected + " actual=" + actual + "). Stopping polls.");
  window.__myxai_stale_page = true;
  document.addEventListener("DOMContentLoaded", function() {
    [window._notifTimer, window._badgePollTimer, window._taskPollTimer].forEach(function(t) {
      if (t) clearInterval(t);
    });
    var b = document.createElement("div");
    b.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:10000;"
      + "background:var(--yellow,#f9e2af);color:var(--base,#1e1e2e);"
      + "padding:10px 20px;text-align:center;font-size:14px;"
      + "border-bottom:1px solid var(--overlay0,#6c7086);";
    b.innerHTML = "\u26a0\ufe0f \u9875\u9762\u7248\u672c\u5df2\u8fc7\u671f\uff0c\u8bf7\u5237\u65b0\u6216\u5173\u95ed\u6b64\u6807\u7b7e\u9875 "
      + '<button onclick="location.reload()" style="margin-left:12px;padding:4px 12px;cursor:pointer;border-radius:4px;border:1px solid currentColor;background:transparent;">\u7acb\u5373\u5237\u65b0</button>';
    document.body.prepend(b);
  });
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
    "setup.welcome":"欢迎使用 Otta",
    "setup.install.title":"安装 nanobot","setup.install.desc":"在终端运行以下命令：",
    "setup.onboard.title":"初始化配置","setup.onboard.desc":"点击下方按钮自动初始化。","setup.onboard.btn":"初始化 nanobot",
    "setup.apikey.title":"配置 API Key","setup.apikey.desc":"前往「设置」页面填写您的 API Key。","setup.apikey.btn":"前往设置",
    "chat.ready":"Otta 已就绪","chat.readyDesc":"输入消息开始对话，我可以帮你搜索信息、编写代码、管理文件等。",
    "chat.placeholder":"输入消息… (Enter 发送, Shift+Enter 换行)",
    "chat.you":"你","chat.noHistory":"暂无历史对话","chat.newChat":"新对话",
    "chat.rename":"重命名","chat.renameTitle":"修改对话标题","chat.renamePlaceholder":"输入新标题",
    "chat.regenerate":"重新回答",
    "chat.rated":"已评价","chat.thankFeedback":"感谢反馈！","chat.willImprove":"已记录，会改进",
    "chat.askDislike":"可以说说哪里不满意吗？（可留空）",
    "chat.error":"错误: ","chat.requestFail":"请求失败: ",
    "chat.executing":"执行中…","chat.execDone":"执行完成","chat.steps":"步",
    "settings.title":"设置","settings.save":"保存配置",
    "settings.tabGeneral":"通用","settings.tabModel":"模型","settings.tabTools":"工具","settings.tabPrivacy":"隐私","settings.tabAdvanced":"高级",
    "settings.smartCore":"智能核心","settings.smartCoreDesc":"意图理解、策略沉淀、执行分析与能力增长——四大核心引擎协同驱动智能决策",
    "settings.closeBehavior":"关闭窗口时","settings.closeMinimize":"最小化到托盘（后台运行）","settings.closeQuit":"完全退出",
    "settings.model":"模型设置","settings.modelName":"模型名称",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"最大工具迭代次数","settings.memoryWindow":"记忆窗口大小",
    "settings.tokenCost":"Token 成本与预警","settings.inputPrice":"输入单价 (元/百万token)","settings.outputPrice":"输出单价 (元/百万token)",
    "settings.dailyLimit":"日使用量预警 (百万token)","settings.monthlyLimit":"月使用量预警 (百万token)",
    "settings.apiKeys":"API 密钥",
    "settings.searchTools":"搜索与工具","settings.baiduKey":"百度搜索 API Key","settings.braveKey":"Brave Search API Key",
    "settings.quotaOnly":"仅使用免费额度","settings.usageToday":"今日已用","settings.quotaExhausted":"额度已用完",
    "settings.searchQuota":"搜索 API 额度","settings.braveQuota":"免费额度","settings.baiduQuota":"免费额度",
    "settings.toolSettings":"工具设置",
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
    "status.scheduler":"调度器","status.schedulerHealthy":"正常","status.schedulerDegraded":"降级",
    "status.available":"可用性","status.installed":"已安装","status.notInstalled":"未安装",
    "status.dbWriteStatus":"数据库写入","status.failed":"失败","status.normal":"正常",
    "status.positiveCases":"正面案例 (👍)","status.negativeCases":"负面案例 (👎)",
    "status.recentPositive":"最近正面","status.recentNegative":"最近负面",
    "system.info":"系统信息","system.device":"设备","system.hostname":"主机名","system.os":"操作系统",
    "system.architecture":"架构","system.processor":"处理器","system.cpu":"CPU","system.cores":"核心",
    "system.frequency":"频率","system.usage":"使用率","system.memory":"内存","system.total":"总计",
    "system.used":"已用","system.available":"可用","system.storage":"存储","system.disk":"磁盘",
    "system.free":"空闲","system.gpu":"显卡","system.noGpu":"未检测到独立显卡","system.network":"网络",
    "system.interfaces":"网络接口","system.sent":"发送","system.received":"接收",
    "system.bootTime":"启动时间","system.uptime":"运行时长","system.physical":"物理","system.logical":"逻辑",
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
    "privacy.dataStorageTitle":"数据存储说明","privacy.localOnly":"仅本地存储","privacy.localOnlyDesc":"对话记录、浏览历史、用户画像、审计日志 — 始终保存在你的设备上，不会发送到任何外部服务。",
    "privacy.keyringSec":"密钥安全存储","privacy.keyringSecDesc":"API Key、邮箱密码等敏感信息通过系统钥匙串加密保存，配置文件中仅存引用。",
    "privacy.sentToApi":"发送到外部 API","privacy.sentToApiDesc":"当前对话消息发送到 LLM 提供商；搜索查询发送到搜索 API。对话历史和画像不会自动发送。",
    "privacy.secretsTitle":"密钥管理","privacy.secretsDesc":"查看当前存储的密钥数量，或一键清除所有已保存的 API Key 和密码。",
    "privacy.clearSecrets":"清除所有密钥","privacy.clearSecretsConfirm":"确定要清除所有已保存的 API Key 和密码吗？清除后需要重新配置。",
    "privacy.secretsCleared":"所有密钥已清除","privacy.backend":"存储后端","privacy.backendKeyring":"系统钥匙串","privacy.backendFile":"加密文件",
    "privacy.storedKeys":"已存储密钥",
    "nav.reports":"报告","nav.apps":"应用",
    "reports.title":"报告","reports.unread":"未读","reports.24h":"24小时","reports.3d":"3天","reports.7d":"7天","reports.30d":"30天","reports.all":"全部",
    "reports.empty":"暂无报告","reports.allRead":"全部已读，去看看其他时间段吧","reports.viewReport":"查看",
    "reports.markAllRead":"全部已读","reports.delete":"删除","reports.deleteOk":"已删除","reports.deleteFail":"删除失败",
    "nav.stats":"统计","stats.todayPrefix":"今日","stats.tokenTitle":"Token 消耗","stats.searchTitle":"搜索 API 调用","stats.costTitle":"消费成本",
    "stats.rangeTotal":"累计","stats.tokenTip":"今日 LLM Token 消耗量","stats.searchTip":"今日各搜索引擎用量 / 额度","stats.costTip":"今日消费成本",
    "stats.noPricing":"未设置 Token 单价","stats.noPricingHint":"请在「设置 → 模型」中配置输入/输出单价",
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
    "er.title":"执行棱镜","er.summary":"今日棱镜","er.runNow":"立即运行",
    "er.totalTasks":"任务数","er.successRate":"成功率",
    "er.singleHitRate":"单任务命中率","er.multiHitRate":"多任务命中率",
    "er.avgAttempts":"平均尝试次数","er.avgTokens":"平均 Token",
    "er.trends":"趋势","er.hitRateTrend":"命中率趋势","er.attemptsTrend":"尝试次数趋势",
    "er.topErrors":"Top 错误码","er.topTools":"Top 工具",
    "er.errorCode":"错误码","er.count":"次数","er.pct":"占比",
    "er.toolName":"工具名称","er.failCount":"失败次数",
    "er.loading":"加载中…","er.noData":"暂无数据",
    "er.running":"正在扫描…","er.runStarted":"棱镜扫描已启动，数据将在几秒后更新",
    "er.runFailed":"扫描失败","er.runDone":"扫描完成，数据已更新","er.runTimeout":"扫描仍在进行中，请稍后手动刷新",
    "er.noErrors":"本日无错误，全部执行成功",
    "er.avgPrefix":"平均","er.avgSuffix":"次/任务","er.avgSuffixPerEff":"次/{n}有效步",
    "er.taskDetail":"评价详情","er.taskContent":"任务内容",
    "er.totalSteps":"步数","er.effectiveSteps":"有效数",
    "er.hitRateCol":"命中率","er.successCol":"是否成功",
    "er.yes":"成功","er.no":"失败",
    "er.stepIndex":"步骤","er.stepArgs":"参数",
    "er.stepStatus":"状态","er.stepEffective":"判定",
    "er.effective":"有效","er.ineffective":"无效",
    "er.config":"设置","er.scheduleTime":"每日扫描时间","er.saveConfig":"保存设置","er.configSaved":"设置已保存","er.configFail":"保存失败",
    "er.avgRemovedSteps":"可省LLM调用","er.candidatesUnit":"条候选",
    "er.goldenCandidates":"候选黄金路径","er.qualityScore":"质量分","er.removedSteps":"可省LLM","er.candidateLen":"候选步数","er.candidateStatus":"状态",
    "ie.title":"意图引擎","ie.switches":"开关配置","ie.thresholds":"阈值调节",
    "ie.routingEnabled":"意图路由",
    "ie.routeConfLow":"路由置信阈值","ie.hintsMaxLen":"Hints 最大长度",
    "ie.trends":"最近 7 天趋势","ie.recentRuns":"最近路由记录",
    "ie.totalRuns":"总路由次数","ie.successRate":"成功率","ie.reuseCount":"复用次数",
    "ie.avgConf":"平均置信度","ie.toolsBefore":"裁剪前工具数","ie.toolsAfter":"裁剪后工具数",
    "ie.reuseRate":"复用率",
    "ie.noRuns":"暂无路由记录","ie.time":"时间","ie.text":"用户输入",
    "ie.route":"路由","ie.mode":"模式","ie.toolsTrim":"工具裁剪","ie.outcome":"结果",
    "ie.healthOverview":"全局健康概览","ie.routingHealth":"路由健康度",
    "ie.avgToolReduction":"平均裁剪率","ie.goldenHitRate":"Golden 命中率",
    "ie.avgLlmCalls":"平均 LLM 调用","ie.avgLatency":"路由耗时",
    "ie.misrouteRate":"疑似误裁剪","ie.routeEffect":"路由效果分析",
    "ie.toolReductionTrend":"工具裁剪率趋势","ie.goldenHitTrend":"Golden 命中率趋势",
    "ie.llmCallTrend":"LLM 调用趋势","ie.patternDist":"模式分布与工具分析",
    "ie.routeLabelDist":"路由标签分布","ie.toolPruneMap":"工具裁剪热力图",
    "ie.tool":"工具","ie.keptCount":"保留次数","ie.prunedCount":"裁剪次数",
    "ie.keptRate":"保留率","ie.execDetail":"单次执行明细","ie.caseKey":"Case Key",
    "ie.goldenHit":"Golden","ie.llmCalls":"LLM次数","ie.latency":"耗时",
    "ie.routeLabels":"路由标签","ie.allowedTools":"保留工具","ie.reductionRate":"裁剪率",
    "ie.planSource":"决策来源","ie.decisionModes":"路由方式","ie.decisions":"执行路径",
    "ie.routingMethod":"路由方式","ie.execPath":"执行路径","ie.riskDist":"风险分布",
    "ie.fallbackRate":"兜底率","ie.misrouteCount":"疑似误路由",
    "ie.good":"良好","ie.fair":"一般","ie.poor":"较差",
    "ie.last7d":"近7天","ie.last14d":"近14天","ie.last30d":"近30天",
    "ie.configAndModels":"配置与模型",
    "ie.intentConfidence":"意图置信度","ie.effectiveSteps":"有效步数","ie.costScore":"Token数",
    "ie.correctCategory":"纠正类别","ie.submitCorrection":"提交纠正","ie.correctionSaved":"纠正已保存","ie.alreadyCorrected":"已纠正",
    "ie.learning":"空闲学习","ie.learningDesc":"夜间利用LLM学习用户语言习惯，白天全程离线","ie.learningEnabled":"启用空闲学习","ie.learningUseLlm":"允许调用LLM","ie.learningSanitize":"PII脱敏","ie.learningMaxSamples":"最大采样数","ie.learningMinRuns":"最小触发查询数","ie.learningMinMisroutes":"最小误路由数",
    "ie.learningRun":"手动执行","ie.learningDryRun":"预览(不调LLM)","ie.learningForce":"强制执行","ie.learningRunning":"执行中...","ie.learningDone":"学习完成","ie.learningFailed":"学习失败",
    "ie.lexicon":"用户词表","ie.lexiconCurrent":"当前词表","ie.lexiconVersions":"历史版本","ie.lexiconRollback":"回滚","ie.lexiconDiff":"对比","ie.lexiconSynonyms":"同义词","ie.lexiconVerbMap":"动词映射","ie.lexiconStopPhrases":"停用短语","ie.lexiconNoData":"暂无词表数据","ie.lexiconSaved":"词表已保存",
    "ie.aliases":"Case Key 别名","ie.aliasAdd":"添加别名","ie.aliasFrom":"别名","ie.aliasTo":"标准Key","ie.aliasNoData":"暂无别名",
    "ie.auditTrail":"审计记录","ie.auditPromptSent":"发送给LLM的内容","ie.auditLlmResponse":"LLM返回内容","ie.auditArtifacts":"学习成果","ie.auditNoRuns":"暂无学习记录",
    "ie.privacy":"隐私说明","ie.privacySentData":"发送的数据","ie.privacyNeverSent":"绝不发送","ie.privacyLearned":"学习的内容","ie.privacyPreview":"预览脱敏效果",
    "ie.privacySent1":"脱敏后的用户查询（已移除邮箱、路径、电话、IP、URL）","ie.privacySent2":"Case Key（意图标识，不含用户数据）","ie.privacySent3":"路由标签（仅类别名称）","ie.privacySent4":"统计汇总（次数、比率）",
    "ie.privacyNever1":"原始文件内容或路径","ie.privacyNever2":"邮箱地址、电话号码","ie.privacyNever3":"API Key 或凭证","ie.privacyNever4":"完整对话历史",
    "ie.privacyLearned1":"同义词映射（用户缩写 → 标准形式）","ie.privacyLearned2":"动词映射（口语动词 → 标准动词）","ie.privacyLearned3":"停用短语（用户特有的填充词）","ie.privacyLearned4":"Case Key 别名（等价意图分组）",
    "ie.privacyStorage":"所有学习数据仅存储在本地，支持版本控制与回滚。",
    "ie.auditDate":"日期","ie.auditStatus":"状态","ie.auditTokens":"Tokens","ie.auditArtifactsSummary":"成果","ie.auditDetail":"详情","ie.auditStartTime":"开始时间","ie.auditDuration":"耗时",
    "ie.auditModel":"模型","ie.selectVersionFirst":"请先选择一个版本","ie.rolledBackTo":"已回滚到","ie.aliasAdded":"别名已添加","ie.aliasRemoved":"别名已移除","ie.fillBothFields":"请填写两个字段",
    "ie.learnTriggerRuns":"查询数","ie.learnTriggerMisroutes":"误路由",
    "ie.statusCompleted":"已完成","ie.statusSuccess":"成功","ie.statusRunning":"运行中","ie.statusSkipped":"已跳过","ie.statusError":"错误","ie.statusDryRun":"预览","ie.statusLocalOnly":"仅本地","ie.statusUnknown":"未知",
  },
  en: {
    "nav.newChat":"New Chat","nav.settings":"Settings","nav.status":"Status","nav.gateway":"Gateway",
    "tasks.btn":"Tasks","tasks.today":"Today's Tasks","tasks.planned":"Planned","tasks.running":"Running","tasks.success":"Done","tasks.failed":"Failed","tasks.pendingCatchup":"Catch-up","tasks.noTasks":"No tasks today","tasks.catchupNote":"catch-up","tasks.runNow":"Run Now","tasks.triggered":"Task triggered","tasks.triggerFail":"Trigger failed",
    "setup.welcome":"Welcome to Otta",
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
    "settings.tabGeneral":"General","settings.tabModel":"Model","settings.tabTools":"Tools","settings.tabPrivacy":"Privacy","settings.tabAdvanced":"Advanced",
    "settings.smartCore":"Smart Core","settings.smartCoreDesc":"Intent understanding, strategy accumulation, execution analytics & capability growth — four core engines powering intelligent decisions",
    "settings.closeBehavior":"On Window Close","settings.closeMinimize":"Minimize to tray (run in background)","settings.closeQuit":"Quit completely",
    "settings.model":"Model Settings","settings.modelName":"Model Name",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"Max Tool Iterations","settings.memoryWindow":"Memory Window Size",
    "settings.tokenCost":"Token Cost & Alerts","settings.inputPrice":"Input Price (¥/M tokens)","settings.outputPrice":"Output Price (¥/M tokens)",
    "settings.dailyLimit":"Daily Alert (M tokens)","settings.monthlyLimit":"Monthly Alert (M tokens)",
    "settings.apiKeys":"API Keys",
    "settings.searchTools":"Search & Tools","settings.baiduKey":"Baidu Search API Key","settings.braveKey":"Brave Search API Key",
    "settings.quotaOnly":"Free quota only","settings.usageToday":"Used today","settings.quotaExhausted":"Quota exhausted",
    "settings.searchQuota":"Search API Quota","settings.braveQuota":"Free Quota","settings.baiduQuota":"Free Quota",
    "settings.toolSettings":"Tool Settings",
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
    "status.scheduler":"Scheduler","status.schedulerHealthy":"Healthy","status.schedulerDegraded":"Degraded",
    "status.available":"Availability","status.installed":"Installed","status.notInstalled":"Not Installed",
    "status.dbWriteStatus":"Database Write","status.failed":"Failed","status.normal":"Normal",
    "status.positiveCases":"Positive (👍)","status.negativeCases":"Negative (👎)",
    "status.recentPositive":"Recent Positive","status.recentNegative":"Recent Negative",
    "system.info":"System Information","system.device":"Device","system.hostname":"Hostname","system.os":"Operating System",
    "system.architecture":"Architecture","system.processor":"Processor","system.cpu":"CPU","system.cores":"Cores",
    "system.frequency":"Frequency","system.usage":"Usage","system.memory":"Memory","system.total":"Total",
    "system.used":"Used","system.available":"Available","system.storage":"Storage","system.disk":"Disk",
    "system.free":"Free","system.gpu":"GPU","system.noGpu":"No dedicated GPU detected","system.network":"Network",
    "system.interfaces":"Network Interfaces","system.sent":"Sent","system.received":"Received",
    "system.bootTime":"Boot Time","system.uptime":"Uptime","system.physical":"Physical","system.logical":"Logical",
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
    "privacy.dataStorageTitle":"Data Storage Info","privacy.localOnly":"Local Only","privacy.localOnlyDesc":"Chat history, browsing history, user profile, audit logs — always stored on your device, never sent to external services.",
    "privacy.keyringSec":"Secure Key Storage","privacy.keyringSecDesc":"API keys, email passwords and other secrets are encrypted via system Keyring. Config files only store references.",
    "privacy.sentToApi":"Sent to External APIs","privacy.sentToApiDesc":"Current chat messages are sent to LLM providers; search queries to search APIs. Chat history and profiles are not sent automatically.",
    "privacy.secretsTitle":"Key Management","privacy.secretsDesc":"View stored secret count, or clear all saved API keys and passwords at once.",
    "privacy.clearSecrets":"Clear All Keys","privacy.clearSecretsConfirm":"Are you sure you want to clear all saved API keys and passwords? You will need to reconfigure them.",
    "privacy.secretsCleared":"All secrets cleared","privacy.backend":"Backend","privacy.backendKeyring":"System Keyring","privacy.backendFile":"Encrypted File",
    "privacy.storedKeys":"Stored keys",
    "nav.reports":"Reports","nav.apps":"Apps",
    "reports.title":"Reports","reports.unread":"Unread","reports.24h":"24h","reports.3d":"3 Days","reports.7d":"7 Days","reports.30d":"30 Days","reports.all":"All",
    "reports.empty":"No reports yet","reports.allRead":"All caught up! Try another time range","reports.viewReport":"View",
    "reports.markAllRead":"Mark all read","reports.delete":"Delete","reports.deleteOk":"Deleted","reports.deleteFail":"Delete failed",
    "nav.stats":"Statistics","stats.todayPrefix":"Today","stats.tokenTitle":"Token Usage","stats.searchTitle":"Search API Calls","stats.costTitle":"Cost",
    "stats.rangeTotal":"Total","stats.tokenTip":"Today's LLM token usage","stats.searchTip":"Today's search usage / quota per engine","stats.costTip":"Today's cost",
    "stats.noPricing":"Token Pricing Not Set","stats.noPricingHint":"Please configure input/output pricing in Settings → Model",
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
    "er.title":"Execution Prism","er.summary":"Today's Prism","er.runNow":"Run Now",
    "er.totalTasks":"Tasks","er.successRate":"Success Rate",
    "er.singleHitRate":"Single Hit Rate","er.multiHitRate":"Multi Hit Rate",
    "er.avgAttempts":"Avg Attempts","er.avgTokens":"Avg Tokens",
    "er.trends":"Trends","er.hitRateTrend":"Hit Rate Trend","er.attemptsTrend":"Attempts Trend",
    "er.topErrors":"Top Errors","er.topTools":"Top Tools",
    "er.errorCode":"Error Code","er.count":"Count","er.pct":"Pct",
    "er.toolName":"Tool Name","er.failCount":"Fail Count",
    "er.loading":"Loading…","er.noData":"No data yet",
    "er.running":"Scanning…","er.runStarted":"Radar scan started, data will update shortly",
    "er.runFailed":"Scan failed","er.runDone":"Scan complete, data updated","er.runTimeout":"Scan still running, refresh later",
    "er.noErrors":"No errors today — all executions succeeded",
    "er.avgPrefix":"avg","er.avgSuffix":"steps/task","er.avgSuffixPerEff":"steps/{n}eff",
    "er.taskDetail":"Task Detail","er.taskContent":"Task",
    "er.totalSteps":"Steps","er.effectiveSteps":"Effective",
    "er.hitRateCol":"Hit Rate","er.successCol":"Success",
    "er.yes":"Yes","er.no":"No",
    "er.stepIndex":"#","er.stepArgs":"Args",
    "er.stepStatus":"Status","er.stepEffective":"Verdict",
    "er.effective":"Effective","er.ineffective":"Ineffective",
    "er.config":"Settings","er.scheduleTime":"Daily Scan Time","er.saveConfig":"Save Settings","er.configSaved":"Settings saved","er.configFail":"Save failed",
    "er.avgRemovedSteps":"LLM Calls Saveable","er.candidatesUnit":"candidates",
    "er.goldenCandidates":"Golden Path Candidates","er.qualityScore":"Quality","er.removedSteps":"LLM Saved","er.candidateLen":"Plan Steps","er.candidateStatus":"Status",
    "ie.title":"Intent Engine","ie.switches":"Switches","ie.thresholds":"Thresholds",
    "ie.routingEnabled":"Intent Routing",
    "ie.routeConfLow":"Route Confidence Threshold","ie.hintsMaxLen":"Hints Max Length",
    "ie.trends":"Last 7 Days Trend","ie.recentRuns":"Recent Routing Logs",
    "ie.totalRuns":"Total Routes","ie.successRate":"Success Rate","ie.reuseCount":"Reuse Count",
    "ie.avgConf":"Avg Confidence","ie.toolsBefore":"Tools Before","ie.toolsAfter":"Tools After",
    "ie.reuseRate":"Reuse Rate",
    "ie.noRuns":"No routing logs yet","ie.time":"Time","ie.text":"User Input",
    "ie.route":"Route","ie.mode":"Mode","ie.toolsTrim":"Tool Trim","ie.outcome":"Outcome",
    "ie.healthOverview":"Health Overview","ie.routingHealth":"Routing Health",
    "ie.avgToolReduction":"Avg Tool Reduction","ie.goldenHitRate":"Golden Hit Rate",
    "ie.avgLlmCalls":"Avg LLM Calls","ie.avgLatency":"Routing Latency",
    "ie.misrouteRate":"Suspected Misroute","ie.routeEffect":"Route Effectiveness",
    "ie.toolReductionTrend":"Tool Reduction Trend","ie.goldenHitTrend":"Golden Hit Rate Trend",
    "ie.llmCallTrend":"LLM Call Trend","ie.patternDist":"Pattern & Tool Analysis",
    "ie.routeLabelDist":"Route Label Distribution","ie.toolPruneMap":"Tool Pruning Heatmap",
    "ie.tool":"Tool","ie.keptCount":"Kept","ie.prunedCount":"Pruned",
    "ie.keptRate":"Kept Rate","ie.execDetail":"Execution Detail","ie.caseKey":"Case Key",
    "ie.goldenHit":"Golden","ie.llmCalls":"LLM Calls","ie.latency":"Latency",
    "ie.routeLabels":"Route Labels","ie.allowedTools":"Allowed Tools","ie.reductionRate":"Reduction",
    "ie.planSource":"Decision Source","ie.decisionModes":"Routing Method","ie.decisions":"Execution Path",
    "ie.routingMethod":"Routing Method","ie.execPath":"Execution Path","ie.riskDist":"Risk Distribution",
    "ie.fallbackRate":"Fallback Rate","ie.misrouteCount":"Suspected Misroutes",
    "ie.good":"Good","ie.fair":"Fair","ie.poor":"Poor",
    "ie.last7d":"7 Days","ie.last14d":"14 Days","ie.last30d":"30 Days",
    "ie.configAndModels":"Config & Models",
    "ie.intentConfidence":"Intent Confidence","ie.effectiveSteps":"Effective Steps","ie.costScore":"Tokens",
    "ie.correctCategory":"Correct Category","ie.submitCorrection":"Submit","ie.correctionSaved":"Correction saved","ie.alreadyCorrected":"Corrected",
    "ie.learning":"Idle Learning","ie.learningDesc":"Use LLM during idle time to learn language habits, stay fully offline during the day","ie.learningEnabled":"Enable Idle Learning","ie.learningUseLlm":"Allow LLM Calls","ie.learningSanitize":"PII Sanitization","ie.learningMaxSamples":"Max Samples","ie.learningMinRuns":"Min Queries to Trigger","ie.learningMinMisroutes":"Min Misroutes to Trigger",
    "ie.learningRun":"Run Now","ie.learningDryRun":"Dry Run (no LLM)","ie.learningForce":"Force Run","ie.learningRunning":"Running...","ie.learningDone":"Learning complete","ie.learningFailed":"Learning failed",
    "ie.lexicon":"User Lexicon","ie.lexiconCurrent":"Current Lexicon","ie.lexiconVersions":"Version History","ie.lexiconRollback":"Rollback","ie.lexiconDiff":"Compare","ie.lexiconSynonyms":"Synonyms","ie.lexiconVerbMap":"Verb Mappings","ie.lexiconStopPhrases":"Stop Phrases","ie.lexiconNoData":"No lexicon data","ie.lexiconSaved":"Lexicon saved",
    "ie.aliases":"Case Key Aliases","ie.aliasAdd":"Add Alias","ie.aliasFrom":"Alias","ie.aliasTo":"Canonical Key","ie.aliasNoData":"No aliases",
    "ie.auditTrail":"Audit Trail","ie.auditPromptSent":"Prompt Sent to LLM","ie.auditLlmResponse":"LLM Response","ie.auditArtifacts":"Artifacts Produced","ie.auditNoRuns":"No learning runs yet",
    "ie.privacy":"Privacy","ie.privacySentData":"Data Sent","ie.privacyNeverSent":"Never Sent","ie.privacyLearned":"What Is Learned","ie.privacyPreview":"Preview Sanitization",
    "ie.privacySent1":"Sanitized user queries (PII removed: emails, paths, phones, IPs, URLs)","ie.privacySent2":"Case keys (intent identifiers, no user data)","ie.privacySent3":"Route labels (category names only)","ie.privacySent4":"Statistical aggregates (counts, rates)",
    "ie.privacyNever1":"Raw file contents or paths","ie.privacyNever2":"Email addresses, phone numbers","ie.privacyNever3":"API keys or credentials","ie.privacyNever4":"Full conversation history",
    "ie.privacyLearned1":"Synonym mappings (user abbreviations → standard forms)","ie.privacyLearned2":"Verb mappings (colloquial verbs → standard verbs)","ie.privacyLearned3":"Stop phrases (user-specific filler words)","ie.privacyLearned4":"Case key aliases (equivalent intent groupings)",
    "ie.privacyStorage":"All learned data stored locally only. Versioned and rollback-able.",
    "ie.auditDate":"Date","ie.auditStatus":"Status","ie.auditTokens":"Tokens","ie.auditArtifactsSummary":"Artifacts","ie.auditDetail":"Detail","ie.auditStartTime":"Start Time","ie.auditDuration":"Duration",
    "ie.auditModel":"Model","ie.selectVersionFirst":"Select a version first","ie.rolledBackTo":"Rolled back to","ie.aliasAdded":"Alias added","ie.aliasRemoved":"Alias removed","ie.fillBothFields":"Fill both fields",
    "ie.learnTriggerRuns":"runs","ie.learnTriggerMisroutes":"misroutes",
    "ie.statusCompleted":"Completed","ie.statusSuccess":"Success","ie.statusRunning":"Running","ie.statusSkipped":"Skipped","ie.statusError":"Error","ie.statusDryRun":"Dry Run","ie.statusLocalOnly":"Local Only","ie.statusUnknown":"Unknown",
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
  // Try i18n module (loaded from backend JSON) first
  try {
    const msg = getI18n().t(key);
    if (msg !== key) return msg;
  } catch(_) {}
  // Fallback to embedded messages
  return (FALLBACK_I18N[_lang] && FALLBACK_I18N[_lang][key]) || (FALLBACK_I18N.zh && FALLBACK_I18N.zh[key]) || key; 
}

function setLanguage(val) {
  localStorage.setItem("nanobot_lang", val);
  _lang = (val === "auto") ? detectLang() : val;
  localStorage.setItem("myxai_locale", _lang);
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = val;
  const radio = document.querySelector(`input[name="lang-radio"][value="${val}"]`);
  if (radio) radio.checked = true;
  applyLanguage();
  try { getI18n().setLocale(_lang).then(() => applyLanguage()); } catch(_) {}
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
  fetch("/api/desk/lang", {method:"POST", headers:authHeaders({"Content-Type":"application/json"}), body: JSON.stringify({lang: _lang})}).catch(()=>{});
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
    const items = await api("/api/notifications", "POST");
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
  if (page === "settings") { loadConfig(); _syncGwSettings(); loadDeskSettings(); switchSettingsTab(_lastSettingsTab || "general"); }
  if (page === "stats") { loadTokenChart(_statsTimeRange); loadSearchChart(_statsTimeRange); loadCostChart(_statsTimeRange); loadCategoryCharts(_statsTimeRange); }
  if (page === "status") {
    loadStatus();
    startStatusAutoRefresh();
  } else {
    stopStatusAutoRefresh();
  }
  if (page === "gateway") loadGatewayStatus();
  if (page === "apps") loadApps();
  if (page === "reports") loadReportsPage();
  if (page === "audit") loadAuditPage();
}

// ── Settings tabs ─────────────────────────────────────────────────────

let _lastSettingsTab = "general";

function switchSettingsTab(tab) {
  _lastSettingsTab = tab;
  document.querySelectorAll(".settings-tab").forEach(b => b.classList.toggle("active", b.dataset.stab === tab));
  document.querySelectorAll(".settings-tab-content").forEach(c => c.classList.toggle("active", c.dataset.tab === tab));
}

async function loadDeskSettings() {
  try {
    const data = await api("/api/desk/settings");
    const radio = document.querySelector(`input[name="close-action"][value="${data.close_action || "minimize"}"]`);
    if (radio) radio.checked = true;
  } catch (_) {}
}

async function saveCloseBehavior(value) {
  try {
    await api("/api/desk/settings", "POST", { close_action: value });
  } catch (_) {
    toast(t("settings.saveFail"), "error");
  }
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
        <div class="welcome-icon">🦦</div>
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
    const elId = appendMessageDOM(msg.role, msg.content, !!msg.markdown, i, msg.feedback || null, isLast, msg.steps || null, msg.audit || null);
    if (msg.decision_meta && elId) _appendDecisionBadge(elId, msg.decision_meta);
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
    let finalDecisionMeta = null;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
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
              let stepItem = data.content;
              try {
                const parsed = JSON.parse(data.content);
                if (parsed && parsed.__tool_call__) {
                  stepItem = { tool: parsed.name, args: parsed.arguments };
                }
              } catch (_e) { /* plain text step */ }
              if (isActive()) {
                if (!progressBlockId) { removeElement(thinkingId); progressBlockId = appendProgressBlock(); }
                progressSteps.push(stepItem);
                addProgressStep(progressBlockId, stepItem);
              } else {
                progressSteps.push(stepItem);
              }
            } else if (data.type === "done") {
              finalContent = data.content;
              if (data.usage) finalUsage = data.usage;
              if (data.audit) finalAudit = data.audit;
              if (data.decision_meta) finalDecisionMeta = data.decision_meta;
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
        decision_meta: finalDecisionMeta || undefined,
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
          if (finalDecisionMeta) _appendDecisionBadge(progressBlockId, finalDecisionMeta);
        }
      } else if (hasThinkingDom && finalContent !== null) {
        _removeAllThinking();
        const msgEl = appendMessageDOM("bot", finalContent, isMd, chatMessages.length - 1, null, true);
        if (finalUsage && msgEl) appendUsageBadge(msgEl, finalUsage);
        if (finalDecisionMeta && msgEl) _appendDecisionBadge(msgEl, finalDecisionMeta);
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

  const avatar = isUser ? "👤" : "🦦";
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

const _PLAN_SOURCE_LABELS = {
  golden_v2_instance: { label: "实例回放", css: "esb-golden-replay" },
  golden_v2_template: { label: "模板回放", css: "esb-golden-replay" },
  golden_replay:      { label: "黄金回放", css: "esb-golden-replay" },
  golden_candidate:   { label: "候选回放", css: "esb-golden-candidate" },
  reuse_plan:         { label: "计划复用", css: "esb-reuse-plan" },
  llm_free:           { label: "自由推理", css: "esb-llm-free" },
};

const _CATEGORY_ICONS = {
  search: "\u{1F50D}", fs: "\u{1F4C1}", math: "\u{1F522}", creative: "\u{270F}\u{FE0F}",
  ask: "\u{2753}", chat: "\u{1F4AC}", system: "\u{2699}\u{FE0F}", browser: "\u{1F310}",
  schedule: "\u{1F4C5}", general: "\u{1F4A1}",
};

function _appendDecisionBadge(msgElId, dm) {
  if (!dm || (!dm.plan_source && !dm.cost_reason && !dm.composite)) return;
  const msgEl = document.getElementById(msgElId);
  if (!msgEl) return;
  const body = msgEl.querySelector(".message-body");
  if (!body) return;
  if (body.querySelector(".exec-source-badge")) return;

  if (dm.plan_source) {
    const info = _PLAN_SOURCE_LABELS[dm.plan_source] || _PLAN_SOURCE_LABELS.llm_free;
    const parts = [];
    if (dm.golden_version != null) parts.push(`v${dm.golden_version}`);
    if (dm.removed_steps > 0) parts.push(`\u526A\u679D -${dm.removed_steps}`);
    if (dm.promoted) parts.push("promoted \u2192 \u9EC4\u91D1");
    parts.push(`\u5C1D\u8BD5 ${dm.attempts_count || 0}`);
    parts.push(`LLM ${dm.llm_attempts || 0}`);

    const badge = document.createElement("div");
    badge.className = `exec-source-badge ${info.css}`;
    badge.innerHTML = `<span class="esb-dot"></span><span class="esb-label">${info.label}</span><span class="esb-detail">${parts.join(" \xB7 ")}</span>`;
    body.appendChild(badge);
  }

  if (dm.cost_reason) {
    const tierLabel = {"turbo": "\u26A1 Turbo", "plus": "\u2795 Plus", "max": "\u{1F525} Max"}[dm.cost_tier] || dm.cost_tier;
    const blocked = dm.cost_blocked;
    const costBadge = document.createElement("div");
    costBadge.className = `exec-source-badge ${blocked ? "esb-cost-blocked" : "esb-cost-downgrade"}`;
    const pctText = dm.daily_usage_pct != null ? `${dm.daily_usage_pct.toFixed(0)}%` : "";
    costBadge.innerHTML = `<span class="esb-dot"></span><span class="esb-label">${blocked ? "\u9884\u7B97\u5DF2\u6EE1" : tierLabel}</span><span class="esb-detail">${dm.cost_reason}${dm.effective_model ? " \xB7 \u6A21\u578B: " + dm.effective_model : ""}${pctText ? " \xB7 \u7528\u91CF: " + pctText : ""}</span>`;
    body.appendChild(costBadge);
  }

  // Composite intent badge — shows multi-step task breakdown
  if (dm.composite && dm.composite.mode === "composite" && dm.composite.intent_count > 1) {
    const ci = dm.composite;
    const wrapper = document.createElement("div");
    wrapper.className = "composite-intent-badge";

    const header = document.createElement("div");
    header.className = "cib-header";
    header.innerHTML = `<span class="cib-icon">\u{1F9E9}</span><span class="cib-title">\u7EC4\u5408\u4EFB\u52A1 \xB7 ${ci.intent_count} \u6B65</span>`;
    header.style.cursor = "pointer";
    wrapper.appendChild(header);

    const detail = document.createElement("div");
    detail.className = "cib-detail";
    detail.style.display = "none";

    ci.intents.forEach(function(seg, idx) {
      const icon = _CATEGORY_ICONS[seg.category] || "\u{1F4A1}";
      const step = document.createElement("div");
      step.className = "cib-step";
      step.innerHTML =
        `<span class="cib-step-num">${idx + 1}</span>` +
        `<span class="cib-step-icon">${icon}</span>` +
        `<span class="cib-step-cat">${seg.category}</span>` +
        `<span class="cib-step-text">${seg.text}</span>` +
        `<span class="cib-step-conf">${(seg.confidence * 100).toFixed(0)}%</span>`;
      detail.appendChild(step);
      if (idx < ci.intents.length - 1 && ci.edges[idx]) {
        const arrow = document.createElement("div");
        arrow.className = "cib-arrow";
        arrow.textContent = ci.edges[idx].type === "parallel" ? "\u2195 \u5E76\u884C" : "\u2193";
        detail.appendChild(arrow);
      }
    });

    wrapper.appendChild(detail);
    header.addEventListener("click", function() {
      detail.style.display = detail.style.display === "none" ? "block" : "none";
      header.classList.toggle("cib-expanded");
    });

    body.appendChild(wrapper);
  }
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
  div.innerHTML = `<div class="message-avatar">🦦</div><div class="message-body"><div class="message-sender">nanobot</div><div class="message-content"><div class="thinking-dots"><span></span><span></span><span></span></div></div></div>`;
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
  div.innerHTML = `<div class="message-avatar">🦦</div>
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
  if (content && typeof content === "object" && content.tool) {
    step.innerHTML = _renderToolCallStep(content);
  } else {
    step.textContent = content;
  }
  steps.appendChild(step);
  const container = document.getElementById("chat-messages");
  if (container) container.scrollTop = container.scrollHeight;
}

function _renderToolCallStep(tc) {
  const name = escapeHtml(tc.tool);
  let argsHtml = "";
  if (tc.args && typeof tc.args === "object") {
    const entries = Object.entries(tc.args);
    if (entries.length) {
      const parts = entries.map(([k, v]) => {
        const val = typeof v === "string" ? v : JSON.stringify(v, null, 2);
        const truncated = val.length > 300 ? val.slice(0, 300) + "…" : val;
        return `<span class="tc-arg-key">${escapeHtml(k)}</span>: <span class="tc-arg-val">${escapeHtml(truncated)}</span>`;
      });
      argsHtml = `<div class="tc-args">${parts.join("<br>")}</div>`;
    }
  }
  return `<span class="tc-name">🔧 ${name}</span>${argsHtml}`;
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
  const stepsHtml = steps.map(s => {
    if (s && typeof s === "object" && s.tool) {
      return `<div class="exec-step">${_renderToolCallStep(s)}</div>`;
    }
    return `<div class="exec-step">${escapeHtml(s)}</div>`;
  }).join("");
  return `<details class="exec-details"${open ? " open" : ""}>
    <summary class="exec-summary"><span class="exec-summary-icon">${icon}</span> <span class="exec-summary-text">${label}</span></summary>
    <div class="exec-steps">${stepsHtml}</div>
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

async function loadTokenCostConfig() {
  try {
    const data = await api("/api/token/cost_config");
    document.getElementById("cfg-input-price").value = data.inputPrice || "";
    document.getElementById("cfg-output-price").value = data.outputPrice || "";
    document.getElementById("cfg-daily-limit").value = data.dailyLimit || "";
    document.getElementById("cfg-monthly-limit").value = data.monthlyLimit || "";
  } catch (e) {
    console.warn("Failed to load token cost config", e);
  }
}

async function loadSearchQuotaConfig() {
  try {
    const data = await api("/api/search/quota_config");
    document.getElementById("cfg-brave-quota").value = data.brave || 1000;
    document.getElementById("cfg-baidu-quota").value = data.baidu || 100;
  } catch (e) {
    console.warn("Failed to load search quota config", e);
  }
}

function fillConfigForm(cfg) {
  const get = (obj, path) => path.reduce((o, k) => (o && o[k] !== undefined ? o[k] : ""), obj);
  document.getElementById("cfg-model").value = get(cfg, ["agents", "defaults", "model"]) || "";
  document.getElementById("cfg-temperature").value = get(cfg, ["agents", "defaults", "temperature"]) || 0.7;
  document.getElementById("temp-value").textContent = document.getElementById("cfg-temperature").value;
  document.getElementById("cfg-max-tokens").value = get(cfg, ["agents", "defaults", "maxTokens"]) || "";
  document.getElementById("cfg-max-iterations").value = get(cfg, ["agents", "defaults", "maxToolIterations"]) || "";
  document.getElementById("cfg-memory-window").value = get(cfg, ["agents", "defaults", "memoryWindow"]) || "";
  document.getElementById("cfg-custom-base").value = get(cfg, ["providers", "openai", "apiBase"]) || "";
  document.getElementById("cfg-custom-key").value = get(cfg, ["providers", "openai", "apiKey"]) || "";
  
  // Load token cost config from separate API
  loadTokenCostConfig();
  
  // Load search quota config from separate API
  loadSearchQuotaConfig();
  
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

  const cfgForJson = JSON.parse(JSON.stringify(cfg));
  const maskKeys = (obj) => {
    if (!obj || typeof obj !== "object") return;
    for (const k of Object.keys(obj)) {
      if (/api_?key/i.test(k) && typeof obj[k] === "string" && obj[k]) {
        obj[k] = obj[k].slice(0, 3) + "***" + obj[k].slice(-3);
      } else if (typeof obj[k] === "object") {
        maskKeys(obj[k]);
      }
    }
  };
  maskKeys(cfgForJson);
  document.getElementById("cfg-json-raw").value = JSON.stringify(cfgForJson, null, 2);

  _loadRoutingToggle();
  _loadGoldenReplayToggle();
}

async function _loadRoutingToggle() {
  try {
    const cfg = await api("/api/ie/golden_config");
    const enabled = cfg.routing_enabled !== false;
    const el = document.getElementById("routing-toggle");
    if (el) el.checked = enabled;
    const st = document.getElementById("routing-status");
    if (st) st.textContent = enabled ? "已启用" : "已关闭";
  } catch (_) {}
}

async function toggleRouting(on) {
  try {
    await fetch("/api/ie/golden_config", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ routing_enabled: on }),
    });
    const st = document.getElementById("routing-status");
    if (st) st.textContent = on ? "已启用" : "已关闭";
  } catch (e) { toast("保存失败: " + e.message, "error"); }
}

async function _loadGoldenReplayToggle() {
  try {
    const cfg = await api("/api/ie/golden_config");
    const enabled = cfg.golden_enabled !== false;
    const el = document.getElementById("golden-replay-toggle");
    if (el) el.checked = enabled;
    const st = document.getElementById("golden-replay-status");
    if (st) st.textContent = enabled ? "已启用" : "已关闭";
  } catch (_) {}
}

async function toggleGoldenReplay(on) {
  try {
    await fetch("/api/ie/golden_config", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ golden_enabled: on }),
    });
    const st = document.getElementById("golden-replay-status");
    if (st) st.textContent = on ? "已启用" : "已关闭";
  } catch (e) { toast("保存失败: " + e.message, "error"); }
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
  setOrDel(["providers", "openai", "apiBase"], document.getElementById("cfg-custom-base").value);
  const customKey = document.getElementById("cfg-custom-key").value;
  if (customKey) set(cfg, ["providers", "openai", "apiKey"], customKey);
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
    // Save nanobot config
    const res = await api("/api/config", "POST", cfg);
    if (res.success) {
      configCache = cfg;
      fillConfigForm(cfg);
      
      // Save token cost config separately
      await saveTokenCostConfig();
      
      // Save search quota config separately
      await saveSearchQuotaConfig();
      
      toast(t("settings.saved"), "success");
    } else { toast(res.error || t("settings.saveFail"), "error"); }
  } catch (e) { toast(t("settings.saveFail") + ": " + e.message, "error"); }
}

async function saveTokenCostConfig() {
  const config = {
    inputPrice: parseFloat(document.getElementById("cfg-input-price").value) || 0,
    outputPrice: parseFloat(document.getElementById("cfg-output-price").value) || 0,
    dailyLimit: parseFloat(document.getElementById("cfg-daily-limit").value) || 0,
    monthlyLimit: parseFloat(document.getElementById("cfg-monthly-limit").value) || 0,
  };
  try {
    await api("/api/token/cost_config", "POST", config);
  } catch (e) {
    console.warn("Failed to save token cost config", e);
    throw e;
  }
}

async function saveSearchQuotaConfig() {
  const config = {
    brave: parseInt(document.getElementById("cfg-brave-quota").value) || 1000,
    baidu: parseInt(document.getElementById("cfg-baidu-quota").value) || 100,
  };
  try {
    await api("/api/search/quota_config", "POST", config);
  } catch (e) {
    console.warn("Failed to save search quota config", e);
    throw e;
  }
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

let _statsTimeRange = 7;

function updateStatsTimeRange(days) {
  _statsTimeRange = days;
  document.querySelectorAll(".stats-time-btn").forEach(btn => {
    btn.classList.toggle("active", Number(btn.dataset.days) === days);
  });
  loadTokenChart(days);
  loadSearchChart(days);
  loadCostChart(days);
  loadCategoryCharts(days);
}

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
  const container = document.getElementById("token-chart-container");
  const totalEl = document.getElementById("token-chart-total");
  if (!container) return;
  try {
    const data = await api(`/api/token/history?days=${days || _statsTimeRange}`);
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
  const container = document.getElementById("search-chart-container");
  const totalEl = document.getElementById("search-chart-total");
  if (!container) return;
  try {
    const data = await api(`/api/search/history?days=${days || _statsTimeRange}`);
    const history = data.history || [];
    const total = data.total || 0;
    if (totalEl) totalEl.textContent = `${t("stats.rangeTotal")} ${_fmtNum(total)} 次`;
    _renderBarChart(container, history, "calls", "次");
  } catch (_) {
    container.innerHTML = `<span style="color:var(--text-dim);font-size:12px">—</span>`;
  }
}

async function loadCostChart(days) {
  const canvas = document.getElementById("cost-chart-canvas");
  const totalEl = document.getElementById("cost-chart-total");
  if (!canvas) return;
  
  // Destroy existing chart
  if (window._costChart) {
    window._costChart.destroy();
    window._costChart = null;
  }
  
  try {
    const data = await api(`/api/token/history?days=${days || _statsTimeRange}`);
    const history = data.cost_history || [];
    const total = data.total_cost || 0;
    
    // Check if pricing is configured (any non-zero cost in history)
    const hasPricing = history.length > 0 && history.some(d => d.cost > 0);
    
    if (!hasPricing) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = '14px sans-serif';
      ctx.fillStyle = 'var(--text-sub)';
      ctx.textAlign = 'center';
      ctx.fillText('💡 ' + t("stats.noPricing"), canvas.width / 2, canvas.height / 2 - 10);
      ctx.font = '12px sans-serif';
      ctx.fillStyle = 'var(--text-dim)';
      ctx.fillText(t("stats.noPricingHint"), canvas.width / 2, canvas.height / 2 + 10);
      if (totalEl) totalEl.textContent = "";
      return;
    }
    
    if (totalEl) totalEl.textContent = `${t("stats.rangeTotal")} ¥${total.toFixed(2)}`;
    
    const labels = history.map(d => d.date.slice(5));
    const costs = history.map(d => d.cost || 0);
    
    const isDark = document.body.classList.contains('dark-theme');
    
    window._costChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: t("stats.costTitle"),
          data: costs,
          borderColor: '#f38ba8',
          backgroundColor: 'rgba(243,139,168,0.1)',
          tension: 0.3,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 5,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `¥${ctx.parsed.y.toFixed(4)}`
            }
          }
        },
        scales: {
          x: {
            ticks: { color: isDark ? '#a6adc8' : '#666', font: { size: 11 } },
            grid: { display: false }
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: isDark ? '#a6adc8' : '#666',
              font: { size: 11 },
              callback: (val) => '¥' + val.toFixed(2)
            },
            grid: { color: isDark ? 'rgba(69,71,90,0.4)' : 'rgba(0,0,0,0.1)' }
          }
        }
      }
    });
  } catch (e) {
    console.warn('loadCostChart error:', e);
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

// ── Category charts (Chart.js) ────────────────────────────────────────

let _categoryPieChart = null;
let _categoryBarChart = null;

const _CHART_COLORS = [
  '#89b4fa', '#a6e3a1', '#f9e2af', '#f38ba8', '#cba6f7',
  '#fab387', '#94e2d5', '#74c7ec', '#f5c2e7', '#b4befe',
];

function _catLabel(key) {
  if (key === 'chat') return t('stats.catChat');
  if (key === 'persona') return '画像更新';
  if (key.startsWith('app_')) {
    const appKey = key.slice(4);
    // Map English app names to localized names
    const appNameMap = {
      'execution_radar': '执行棱镜',
      'healthcheck': '执行棱镜',  // legacy
      'strategy_hub': '策略中枢',
    };
    return appNameMap[appKey] || appKey;
  }
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
  const pieCanvas = document.getElementById('category-pie-chart');
  const barCanvas = document.getElementById('category-bar-chart');
  if (!pieCanvas && !barCanvas) return;
  try {
    const data = await api(`/api/usage/categories?days=${days || _statsTimeRange}`);
    const cats = data.categories || {};
    const labels = [], values = [], avgValues = [], colors = [];
    let ci = 0;
    for (const [k, v] of Object.entries(cats)) {
      const total = (v.input || 0) + (v.output || 0);
      // Skip categories with zero usage
      if (total === 0) continue;
      
      labels.push(_catLabel(k));
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

let _monitorPrev = null;  // previous network sample for speed calc

function _monitorBarClass(pct, highAt) { return pct > highAt ? 'high' : pct > 50 ? 'medium' : 'low'; }

function _formatSpeed(bytesPerSec) {
  if (bytesPerSec >= 1048576) return (bytesPerSec / 1048576).toFixed(1) + ' MB/s';
  if (bytesPerSec >= 1024) return (bytesPerSec / 1024).toFixed(1) + ' KB/s';
  return bytesPerSec.toFixed(0) + ' B/s';
}

function _buildMonitorHtml(mon) {
  const upSpeed = mon._upSpeed !== undefined ? _formatSpeed(mon._upSpeed) : '—';
  const downSpeed = mon._downSpeed !== undefined ? _formatSpeed(mon._downSpeed) : '—';
  return `<div class="status-card system-monitor" id="monitor-panel" style="grid-column: 1 / -1">
    <h3>💻 ${t("system.info")}</h3>
    <div class="monitor-grid">
      <div class="monitor-item">
        <div class="monitor-label">${t("system.cpu")}</div>
        <div class="monitor-value">
          <div class="monitor-bar-bg"><div class="monitor-bar ${_monitorBarClass(mon.cpu_percent, 80)}" id="mon-cpu-bar" style="width:${mon.cpu_percent}%"></div></div>
          <span class="monitor-percent" id="mon-cpu-text">${mon.cpu_percent.toFixed(1)}%</span>
        </div>
      </div>
      <div class="monitor-item">
        <div class="monitor-label">${t("system.memory")}</div>
        <div class="monitor-value">
          <div class="monitor-bar-bg"><div class="monitor-bar ${_monitorBarClass(mon.memory.percent, 80)}" id="mon-mem-bar" style="width:${mon.memory.percent}%"></div></div>
          <span class="monitor-percent" id="mon-mem-text">${mon.memory.percent.toFixed(1)}% (${mon.memory.used_gb.toFixed(1)}/${mon.memory.total_gb.toFixed(1)} GB)</span>
        </div>
      </div>
      <div class="monitor-item">
        <div class="monitor-label">${t("system.disk")}</div>
        <div class="monitor-value">
          <div class="monitor-bar-bg"><div class="monitor-bar ${_monitorBarClass(mon.disk.percent, 85)}" id="mon-disk-bar" style="width:${mon.disk.percent}%"></div></div>
          <span class="monitor-percent" id="mon-disk-text">${mon.disk.percent.toFixed(1)}% (${mon.disk.used_gb.toFixed(1)}/${mon.disk.total_gb.toFixed(1)} GB)</span>
        </div>
      </div>
      <div class="monitor-item">
        <div class="monitor-label">${t("system.network")}</div>
        <div class="monitor-value monitor-net-value" id="mon-net-box">
          <span class="monitor-net-item">↑ <span id="mon-net-up">${upSpeed}</span></span>
          <span class="monitor-net-item">↓ <span id="mon-net-down">${downSpeed}</span></span>
        </div>
      </div>
    </div>
  </div>`;
}

function _updateMonitorDom(mon) {
  const bar = (id, pct, highAt) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = pct + '%';
    el.className = 'monitor-bar ' + _monitorBarClass(pct, highAt);
  };
  const txt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  bar('mon-cpu-bar', mon.cpu_percent, 80);
  txt('mon-cpu-text', mon.cpu_percent.toFixed(1) + '%');

  bar('mon-mem-bar', mon.memory.percent, 80);
  txt('mon-mem-text', `${mon.memory.percent.toFixed(1)}% (${mon.memory.used_gb.toFixed(1)}/${mon.memory.total_gb.toFixed(1)} GB)`);

  bar('mon-disk-bar', mon.disk.percent, 85);
  txt('mon-disk-text', `${mon.disk.percent.toFixed(1)}% (${mon.disk.used_gb.toFixed(1)}/${mon.disk.total_gb.toFixed(1)} GB)`);

  if (mon._upSpeed !== undefined) {
    txt('mon-net-up', _formatSpeed(mon._upSpeed));
    txt('mon-net-down', _formatSpeed(mon._downSpeed));
  }
}

function _calcNetSpeed(mon) {
  if (!mon.network) return;
  const now = Date.now();
  if (_monitorPrev && _monitorPrev.network) {
    const dt = (now - _monitorPrev._ts) / 1000;
    if (dt > 0) {
      mon._upSpeed = Math.max(0, (mon.network.bytes_sent - _monitorPrev.network.bytes_sent) / dt);
      mon._downSpeed = Math.max(0, (mon.network.bytes_recv - _monitorPrev.network.bytes_recv) / dt);
    }
  }
  mon._ts = now;
  _monitorPrev = mon;
}

async function loadStatus() {
  const grid = document.getElementById("status-grid");
  grid.innerHTML = `<div class="status-card"><div class="status-label">${t("status.loading")}</div></div>`;

  try {
    const data = await api("/api/status");
    if (data.error) { grid.innerHTML = `<div class="status-card"><div class="status-value err">${data.error}</div></div>`; return; }

    let html = "";

    // Monitor panel placeholder (will be populated by first refresh)
    if (data.monitor && data.monitor.available) {
      _calcNetSpeed(data.monitor);
      html += _buildMonitorHtml(data.monitor);
    } else if (data.monitor && !data.monitor.available) {
      html += `<div class="status-card" style="grid-column: 1 / -1">
        <div style="padding:12px;background:var(--bg-dark);border-radius:6px;font-size:12px;color:var(--yellow)">
          💡 ${t("system.info")}: <code>pip install psutil</code> ${_lang === 'zh' ? '启用实时监控' : 'to enable monitoring'}
        </div>
      </div>`;
    }

    html += statusCard(t("status.configFile"), data.config_path, data.config_exists ? "ok" : "err");
    html += statusCard(t("status.workspace"), data.workspace, data.workspace_exists ? "ok" : "warn");
    html += statusCard(t("status.currentModel"), data.model, "ok");

    // LLM Providers — backend already filters to configured-only
    if (data.providers && data.providers.length > 0) {
      let provHtml = '<div class="provider-list">';
      data.providers.forEach((p) => {
        provHtml += `<div class="provider-row"><span>${p.label || p.name}</span><span class="badge badge-ok">${t("status.configured")}</span></div>`;
      });
      provHtml += "</div>";
      html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.providers")}</h3>${provHtml}</div>`;
    }

    // Channels — backend already filters to enabled-only
    if (data.channels && data.channels.length > 0) {
      let chHtml = '<div class="channel-list">';
      data.channels.forEach((c) => {
        chHtml += `<div class="channel-row"><span>${CHANNEL_NAMES[c.name] || c.name}</span><span class="badge badge-ok">${t("status.enabled")}</span></div>`;
      });
      chHtml += "</div>";
      html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.channels")}</h3>${chHtml}</div>`;
    }

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

    // Scheduler health
    if (data.scheduler) {
      const sch = data.scheduler;
      let schedBadge = sch.degraded 
        ? `<span class="badge badge-off" style="margin-left:8px">⚠️ ${t("status.schedulerDegraded")}</span>`
        : `<span class="badge badge-ok" style="margin-left:8px">${t("status.schedulerHealthy")}</span>`;
      
      let schedHtml = '<div class="provider-list">';
      schedHtml += `<div class="provider-row"><span>Croniter ${t("status.available")}</span><span class="badge ${sch.croniter_available ? 'badge-ok' : 'badge-off'}">${sch.croniter_available ? t("status.installed") : t("status.notInstalled")}</span></div>`;
      schedHtml += `<div class="provider-row"><span>${t("status.dbWriteStatus")}</span><span class="badge ${sch.db_write_failed ? 'badge-off' : 'badge-ok'}">${sch.db_write_failed ? t("status.failed") : t("status.normal")}</span></div>`;
      schedHtml += '</div>';
      
      if (sch.last_error) {
        schedHtml += `<div style="margin-top:8px;padding:8px;background:var(--bg-dark);border-radius:6px;font-size:11px;color:var(--red);font-family:monospace">${escapeHtml(sch.last_error)}</div>`;
      }
      
      if (!sch.croniter_available) {
        schedHtml += `<div style="margin-top:8px;padding:8px;background:var(--bg-dark);border-radius:6px;font-size:11px;color:var(--yellow)"><code>pip install croniter</code></div>`;
      }
      
      html += `<div class="status-card" style="grid-column: 1 / -1"><h3>${t("status.scheduler")} ${schedBadge}</h3>${schedHtml}</div>`;
    }

    grid.innerHTML = html;
  } catch (e) {
    grid.innerHTML = `<div class="status-card"><div class="status-value err">${t("status.loadFail")}${e.message}</div></div>`;
  }
}

async function _refreshMonitor() {
  try {
    const mon = await api("/api/monitor");
    if (!mon || !mon.available) return;
    _calcNetSpeed(mon);
    _updateMonitorDom(mon);
  } catch (_) {}
}

let _statusRefreshInterval = null;

function startStatusAutoRefresh() {
  stopStatusAutoRefresh();
  _statusRefreshInterval = setInterval(() => {
    if (currentPage === "status") _refreshMonitor();
  }, 3000);
}

function stopStatusAutoRefresh() {
  if (_statusRefreshInterval) { clearInterval(_statusRefreshInterval); _statusRefreshInterval = null; }
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
    const items = await api("/api/notifications", "POST");
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

const _ADVANCED_SETTINGS_APPS = new Set(["intent_engine", "strategy_hub", "execution_radar", "cap_forest"]);
let _currentAppDetailId = null;

function goBackFromAppDetail() {
  if (_ADVANCED_SETTINGS_APPS.has(_currentAppDetailId)) {
    switchPage('settings');
    switchSettingsTab('advanced');
  } else {
    switchPage('apps');
  }
  _currentAppDetailId = null;
}

function renderApps(apps) {
  apps = apps.filter(a => !_ADVANCED_SETTINGS_APPS.has(a.id));
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
  _currentAppDetailId = appId;
  if (appId === "daily_digest") { await openDigestDetail(); return; }
  if (appId === "email_summary") { await openEmailDetail(); return; }
  if (appId === "execution_radar") { await openExecutionRadarDetail(); return; }
  if (appId === "intent_engine") { await openIntentEngineDetail(); return; }
  if (appId === "strategy_hub") { await openStrategyHubDetail(); return; }
  if (appId === "cap_forest") { await openCapForestDetail(); return; }
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

// ── Execution Prism Detail ────────────────────────────────────────────
let _erChart1 = null, _erChart2 = null;

async function openExecutionRadarDetail() {
  document.getElementById("app-detail-title").textContent = `💎 ${t("er.title")}`;
  switchPage("app-detail");
  const container = document.getElementById("app-detail-content");

  let hcConfig = {};
  try { hcConfig = await api("/api/apps/execution_radar/config"); } catch (_) {}
  const scheduleTime = hcConfig.schedule_time || "02:00";

  container.innerHTML = `
    <div class="app-detail-section" style="margin-bottom:18px">
      <div class="digest-status-bar" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <span style="font-weight:600">${t("er.summary")}</span>
        <input type="date" id="er-date-picker" value="${new Date().toISOString().slice(0,10)}" style="padding:4px 8px;border-radius:6px;border:1px solid var(--bg-surface1);background:var(--bg-surface0);color:var(--text);font-size:12px" onchange="switchErDate(this.value)">
        <button class="btn btn-sm" id="er-run-btn" onclick="runExecutionRadar()">${t("er.runNow")}</button>
        <span id="er-run-indicator" style="font-size:12px;color:var(--subtext0);display:none"></span>
      </div>
    </div>

    <div class="digest-config-grid" id="er-summary-cards" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:22px">
      <div class="er-card"><div class="er-card-label">${t("er.totalTasks")}</div><div class="er-card-value" id="er-total-tasks">--</div></div>
      <div class="er-card"><div class="er-card-label">${t("er.successRate")}</div><div class="er-card-value" id="er-success-rate">--</div></div>
      <div class="er-card"><div class="er-card-label">${t("er.singleHitRate")}</div><div class="er-card-value" id="er-single-hit">--</div><div class="er-card-sub" id="er-single-avg">--</div></div>
      <div class="er-card"><div class="er-card-label">${t("er.multiHitRate")}</div><div class="er-card-value" id="er-multi-hit">--</div><div class="er-card-sub" id="er-multi-avg">--</div></div>
      <div class="er-card"><div class="er-card-label">${t("er.avgRemovedSteps")}</div><div class="er-card-value" id="er-avg-removed">--</div><div class="er-card-sub" id="er-candidates-count">--</div></div>
    </div>

    <div class="er-golden-kpi-row" id="er-golden-kpi-row">
      <div class="er-golden-card"><div class="er-card-label">黄金回放占比</div><div class="er-card-value" id="er-golden-replay-rate">--</div></div>
      <div class="er-golden-card"><div class="er-card-label">候选回放占比</div><div class="er-card-value" id="er-golden-candidate-rate">--</div></div>
      <div class="er-golden-card"><div class="er-card-label">平均 LLM 次数</div><div class="er-card-value" id="er-avg-llm">--</div></div>
      <div class="er-golden-card"><div class="er-card-label">平均尝试次数</div><div class="er-card-value" id="er-avg-attempts-count">--</div></div>
      <div class="er-golden-card"><div class="er-card-label">可省 LLM 调用</div><div class="er-card-value" id="er-avg-removed-golden">--</div></div>
    </div>

    <div class="app-detail-section" style="margin-bottom:18px">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;cursor:pointer" onclick="toggleErCandidates()">
        <span style="font-weight:600">${t("er.goldenCandidates")}</span>
        <span id="er-candidates-toggle" style="font-size:12px;color:var(--subtext0)">▼</span>
      </div>
      <div id="er-candidates-panel" style="display:none"><div class="er-table-placeholder">${t("er.loading")}</div></div>
    </div>

    <div class="app-detail-section" style="margin-bottom:18px">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;cursor:pointer" onclick="toggleErTaskDetail()">
        <span style="font-weight:600">${t("er.taskDetail")}</span>
        <span id="er-task-detail-toggle" style="font-size:12px;color:var(--subtext0)">▼</span>
      </div>
      <div id="er-task-detail" style="display:none"><div class="er-table-placeholder">${t("er.loading")}</div></div>
    </div>

    <div class="app-detail-section" style="margin-bottom:18px">
      <h3>${t("er.config")}</h3>
      <div class="digest-config-grid">
        <div class="form-group">
          <label>${t("er.scheduleTime")}</label>
          <input type="time" id="er-schedule-time" value="${_escAttr(scheduleTime)}" />
        </div>
      </div>
      <div class="digest-actions" style="margin-top:10px">
        <button class="btn btn-primary" onclick="saveErConfig()">${t("er.saveConfig")}</button>
      </div>
    </div>

    <div class="app-detail-section" style="margin-bottom:18px">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px">
        <span style="font-weight:600">${t("er.trends")}</span>
        <button class="btn btn-xs er-window-btn active" data-w="7" onclick="switchErWindow(7)">7d</button>
        <button class="btn btn-xs er-window-btn" data-w="30" onclick="switchErWindow(30)">30d</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
        <div style="position:relative;height:260px"><canvas id="er-chart-hitrate"></canvas></div>
        <div style="position:relative;height:260px"><canvas id="er-chart-attempts"></canvas></div>
        <div style="position:relative;height:260px" id="er-tab-tools"><div class="er-table-placeholder">${t("er.loading")}</div></div>
      </div>
    </div>
  `;

  await _refreshAllErPanels();
}

async function saveErConfig() {
  const config = {
    schedule_time: document.getElementById("er-schedule-time").value || "02:00",
  };
  try {
    const res = await api("/api/apps/execution_radar/config", "POST", config);
    if (res.success) {
      toast(t("er.configSaved"), "success");
      const app = _appsCache.find(a => a.id === "execution_radar");
      if (app) app.config = config;
    } else {
      toast(res.error || t("er.configFail"), "error");
    }
  } catch (e) { toast(t("er.configFail") + ": " + e.message, "error"); }
}

function _getErDate() {
  const picker = document.getElementById("er-date-picker");
  return picker ? picker.value : new Date().toISOString().slice(0,10);
}

async function _refreshAllErPanels() {
  const d = _getErDate();
  await loadErSummary(d);
  await loadErGoldenStats();
  const activeW = document.querySelector(".er-window-btn.active");
  const window = activeW ? parseInt(activeW.dataset.w) : 7;
  await loadErTrends(window);
  await loadErTopTools(d, window);
  await loadErTaskDetail(d);
  await loadErCandidates(d);
}

async function loadErGoldenStats() {
  try {
    const d = await api("/api/ie/golden_stats");
    const _v = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    _v("er-golden-replay-rate", (d.golden_replay_rate || 0) + "%");
    _v("er-golden-candidate-rate", (d.golden_candidate_rate || 0) + "%");
    _v("er-avg-llm", d.avg_llm_attempts != null ? d.avg_llm_attempts : "--");
    _v("er-avg-attempts-count", d.avg_attempts_count != null ? d.avg_attempts_count : "--");
    _v("er-avg-removed-golden", d.avg_removed_steps != null ? d.avg_removed_steps : "--");
  } catch (e) { console.warn("er golden stats", e); }
}

function switchErDate(dateStr) {
  _refreshAllErPanels();
}

async function loadErSummary(dateStr) {
  try {
    const dt = dateStr || _getErDate();
    const d = await api(`/api/apps/execution_radar/summary?date=${dt}`);
    const inst = d.instrumented_tasks || 0;
    const total = d.total_tasks || 0;
    document.getElementById("er-total-tasks").textContent = inst > 0 ? (inst < total ? `${inst} / ${total}` : `${inst}`) : (total > 0 ? `0 / ${total}` : "0");
    document.getElementById("er-success-rate").textContent = (d.success_rate || 0) + "%";
    document.getElementById("er-single-hit").textContent = (d.single_hit_rate || 0) + "%";
    const sa = d.single_avg_attempts || 0;
    document.getElementById("er-single-avg").textContent = sa > 0 ? `${t("er.avgPrefix")} ${sa} ${t("er.avgSuffix")}` : "-";
    document.getElementById("er-multi-hit").textContent = (d.multi_hit_rate || 0) + "%";
    const ma = d.multi_avg_attempts || 0;
    const mae = d.multi_avg_effective || 0;
    document.getElementById("er-multi-avg").textContent = ma > 0 ? `${t("er.avgPrefix")} ${ma} ${t("er.avgSuffixPerEff").replace("{n}", mae)}` : "-";
    const avgRemoved = d.avg_removed_steps || 0;
    document.getElementById("er-avg-removed").textContent = avgRemoved > 0 ? avgRemoved.toFixed(1) : "0";
    const cg = d.candidates_generated || 0;
    const llmSave = d.total_llm_saveable || 0;
    document.getElementById("er-candidates-count").textContent = cg > 0 ? `${cg} ${t("er.candidatesUnit")}${llmSave > 0 ? ` · 可省${llmSave}次LLM` : ""}` : "-";
    const reportEl = document.getElementById("er-report-text");
    if (d.report_text) {
      reportEl.style.display = "block";
      reportEl.textContent = d.report_text;
    } else {
      reportEl.style.display = "none";
    }
  } catch (e) { console.warn("er summary", e); }
}

async function loadErTrends(window) {
  try {
    const dt = _getErDate();
    const d = await api(`/api/apps/execution_radar/trends?window=${window}&date=${dt}`);
    _renderErHitRateChart(d);
    _renderErAttemptsChart(d);
  } catch (e) { console.warn("er trends", e); }
}

function _renderErHitRateChart(d) {
  const canvas = document.getElementById("er-chart-hitrate");
  if (!canvas) return;
  if (_erChart1) { _erChart1.destroy(); _erChart1 = null; }
  const labels = (d.dates || []).map(x => x.slice(5));
  _erChart1 = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: t("er.singleHitRate"), data: d.single_hit_rates || [], borderColor: "#10b981", backgroundColor: "rgba(16,185,129,0.08)", tension: 0.3, fill: true, pointRadius: 3 },
        { label: t("er.multiHitRate"), data: d.multi_hit_rates || [], borderColor: "#6366f1", backgroundColor: "rgba(99,102,241,0.08)", tension: 0.3, fill: true, pointRadius: 3 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                 title: { display: true, text: t("er.hitRateTrend"), font: { size: 13 } } },
      scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => v + "%" } } },
    },
  });
}

function _renderErAttemptsChart(d) {
  const canvas = document.getElementById("er-chart-attempts");
  if (!canvas) return;
  if (_erChart2) { _erChart2.destroy(); _erChart2 = null; }
  const labels = (d.dates || []).map(x => x.slice(5));
  _erChart2 = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: t("er.avgAttempts"), data: d.avg_attempts || [], borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.08)", tension: 0.3, fill: true, pointRadius: 3 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                 title: { display: true, text: t("er.attemptsTrend"), font: { size: 13 } } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

async function loadErTopTools(dateStr, window = 7) {
  try {
    const dt = dateStr || _getErDate();
    const d = await api(`/api/apps/execution_radar/top_tools?date=${dt}&window=${window}`);
    const el = document.getElementById("er-tab-tools");
    if (!d.tools || d.tools.length === 0) {
      el.innerHTML = `<div class="er-table-placeholder">${t("er.noData")}</div>`;
      return;
    }
    let html = `<div style="padding:8px;overflow-y:auto;max-height:240px"><table class="er-table"><thead><tr><th>#</th><th>${t("er.toolName")}</th><th>${t("er.count")}</th><th>${t("er.failCount")}</th></tr></thead><tbody>`;
    d.tools.slice(0, 8).forEach((e, i) => {
      html += `<tr><td>${i+1}</td><td><code style="font-size:11px">${e.tool_name}</code></td><td>${e.cnt}</td><td>${e.fail_cnt || 0}</td></tr>`;
    });
    html += "</tbody></table></div>";
    el.innerHTML = html;
  } catch (e) { console.warn("er tools", e); }
}

function switchErWindow(w) {
  document.querySelectorAll(".er-window-btn").forEach(b => b.classList.toggle("active", parseInt(b.dataset.w) === w));
  loadErTrends(w);
  const d = _getErDate();
  loadErTopTools(d, w);
}

function toggleErTaskDetail() {
  const panel = document.getElementById("er-task-detail");
  const toggle = document.getElementById("er-task-detail-toggle");
  if (panel.style.display === "none") {
    panel.style.display = "block";
    toggle.textContent = "▲";
  } else {
    panel.style.display = "none";
    toggle.textContent = "▼";
  }
}

function toggleErCandidates() {
  const panel = document.getElementById("er-candidates-panel");
  const toggle = document.getElementById("er-candidates-toggle");
  if (panel.style.display === "none") {
    panel.style.display = "block";
    toggle.textContent = "▲";
  } else {
    panel.style.display = "none";
    toggle.textContent = "▼";
  }
}

async function loadErCandidates(dateStr) {
  try {
    const dt = dateStr || _getErDate();
    const d = await api(`/api/apps/execution_radar/golden_candidates?date=${dt}&limit=10`);
    const el = document.getElementById("er-candidates-panel");
    if (!d.candidates || d.candidates.length === 0) {
      el.innerHTML = `<div class="er-table-placeholder">${t("er.noData")}</div>`;
      return;
    }
    let html = `<table class="er-table"><thead><tr>
      <th style="width:30px"></th>
      <th>#</th>
      <th>${t("er.taskContent")}</th>
      <th>${t("er.qualityScore")}</th>
      <th>${t("er.totalSteps")}</th>
      <th>${t("er.candidateLen")}</th>
      <th>${t("er.removedSteps")}</th>
      <th>${t("er.candidateStatus")}</th>
    </tr></thead><tbody>`;
    d.candidates.forEach((c, i) => {
      const statusBadge = c.status === "promoted"
        ? `<span class="er-badge er-badge-ok">${c.status}</span>`
        : `<span class="er-badge er-badge-dim">${c.status}</span>`;
      const userText = _escHtml((c.user_text || "").slice(0, 50));
      html += `<tr class="er-task-row" onclick="toggleErCandidatePlan(this)" style="cursor:pointer">
        <td><span class="er-arrow">▶</span></td>
        <td>${i + 1}</td>
        <td title="${_escHtml(c.user_text || "")}">${userText}</td>
        <td>${c.quality_score}</td>
        <td>${c.original_steps || "-"}</td>
        <td>${c.candidate_len}</td>
        <td>${c.llm_calls_saved || c.removed_steps || 0}</td>
        <td>${statusBadge}</td>
      </tr>`;
      const planSteps = c.candidate_plan || [];
      let planHtml = `<table class="er-table er-steps-inner"><thead><tr>
        <th>${t("er.stepIndex")}</th><th>${t("er.toolName")}</th><th>${t("er.stepArgs")}</th>
      </tr></thead><tbody>`;
      planSteps.forEach((s, si) => {
        let argsPreview = "";
        try {
          const parsed = typeof s.args_json === "string" ? JSON.parse(s.args_json) : s.args_json;
          const keys = Object.keys(parsed || {});
          if (keys.length > 0) argsPreview = String(parsed[keys[0]] || "").slice(0, 80);
        } catch (_) { argsPreview = String(s.args_json || "").slice(0, 80); }
        planHtml += `<tr><td>${si + 1}</td><td><code>${_escHtml(s.tool_name || "")}</code></td><td class="er-args-cell" title="${_escHtml(s.args_json || "")}">${_escHtml(argsPreview)}</td></tr>`;
      });
      planHtml += `</tbody></table>`;
      html += `<tr class="er-steps-row" style="display:none"><td colspan="8"><div class="er-steps-container">${planHtml}</div></td></tr>`;
    });
    html += `</tbody></table>`;
    el.innerHTML = html;
  } catch (e) { console.warn("er candidates", e); }
}

function toggleErCandidatePlan(row) {
  const next = row.nextElementSibling;
  if (!next || !next.classList.contains("er-steps-row")) return;
  const arrow = row.querySelector(".er-arrow");
  if (next.style.display === "none") {
    next.style.display = "table-row";
    if (arrow) arrow.textContent = "▼";
  } else {
    next.style.display = "none";
    if (arrow) arrow.textContent = "▶";
  }
}

async function loadErTaskDetail(dateStr) {
  try {
    const dt = dateStr || _getErDate();
    const d = await api(`/api/apps/execution_radar/tasks?date=${dt}`);
    const el = document.getElementById("er-task-detail");
    if (!d.tasks || d.tasks.length === 0) {
      el.innerHTML = `<div class="er-table-placeholder">${t("er.noData")}</div>`;
      return;
    }
    let html = `<table class="er-table er-task-table"><thead><tr>
      <th style="width:30px"></th>
      <th>#</th>
      <th>${t("er.taskContent")}</th>
      <th>${t("er.totalSteps")}</th>
      <th>${t("er.effectiveSteps")}</th>
      <th>${t("er.hitRateCol")}</th>
      <th>${t("er.successCol")}</th>
    </tr></thead><tbody>`;
    d.tasks.forEach((task, i) => {
      const hasSteps = task.steps && task.steps.length > 0;
      const toggleAttr = hasSteps ? `onclick="toggleErSteps(this)" style="cursor:pointer"` : "";
      const arrow = hasSteps ? `<span class="er-arrow">▶</span>` : `<span class="er-arrow" style="visibility:hidden">▶</span>`;
      const successIcon = task.success ? `<span class="er-badge er-badge-ok">${t("er.yes")}</span>` : `<span class="er-badge er-badge-fail">${t("er.no")}</span>`;
      const hitStr = task.success && task.total_steps > 0 ? task.hit_rate + "%" : "-";
      const userText = _escHtml((task.user_text || "").slice(0, 60));
      html += `<tr class="er-task-row" ${toggleAttr}>
        <td>${arrow}</td>
        <td>${i + 1}</td>
        <td title="${_escHtml(task.user_text || "")}">${userText}</td>
        <td>${task.total_steps}</td>
        <td>${task.success ? task.effective_count : "-"}</td>
        <td>${hitStr}</td>
        <td>${successIcon}</td>
      </tr>`;
      if (hasSteps) {
        html += `<tr class="er-steps-row" style="display:none"><td colspan="7"><div class="er-steps-container">`;
        html += `<table class="er-table er-steps-inner"><thead><tr>
          <th>${t("er.stepIndex")}</th>
          <th>${t("er.toolName")}</th>
          <th>${t("er.stepArgs")}</th>
          <th>${t("er.stepStatus")}</th>
          <th>${t("er.stepEffective")}</th>
        </tr></thead><tbody>`;
        task.steps.forEach(s => {
          const statusBadge = s.status === "ok"
            ? `<span class="er-badge er-badge-ok">OK</span>`
            : `<span class="er-badge er-badge-fail">${s.error_code || s.status}</span>`;
          const effBadge = s.effective
            ? `<span class="er-badge er-badge-ok">${t("er.effective")}</span>`
            : `<span class="er-badge er-badge-dim">${t("er.ineffective")}</span>`;
          let argsPreview = "";
          try {
            const parsed = JSON.parse(s.args || "{}");
            const keys = Object.keys(parsed);
            if (keys.length > 0) {
              const val = String(parsed[keys[0]] || "").slice(0, 60);
              argsPreview = val + (String(parsed[keys[0]] || "").length > 60 ? "…" : "");
            }
          } catch (_) { argsPreview = (s.args || "").slice(0, 60); }
          html += `<tr>
            <td>${s.index + 1}</td>
            <td><code>${s.tool || "-"}</code></td>
            <td class="er-args-cell" title="${_escHtml(s.args || "")}">${_escHtml(argsPreview)}</td>
            <td>${statusBadge}</td>
            <td>${effBadge}</td>
          </tr>`;
        });
        html += `</tbody></table></div></td></tr>`;
      }
    });
    html += "</tbody></table>";
    el.innerHTML = html;
  } catch (e) { console.warn("er task detail", e); }
}

function toggleErSteps(rowEl) {
  const stepsRow = rowEl.nextElementSibling;
  if (!stepsRow || !stepsRow.classList.contains("er-steps-row")) return;
  const isHidden = stepsRow.style.display === "none";
  stepsRow.style.display = isHidden ? "table-row" : "none";
  const arrow = rowEl.querySelector(".er-arrow");
  if (arrow) arrow.textContent = isHidden ? "▼" : "▶";
}

function _escHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

async function runExecutionRadar() {
  const btn = document.getElementById("er-run-btn");
  const indicator = document.getElementById("er-run-indicator");
  if (!btn) return;
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = t("er.running");
  btn.classList.add("btn-loading");
  if (indicator) { indicator.style.display = "inline"; indicator.textContent = ""; }

  try {
    const dateStr = _getErDate();
    await api("/api/apps/execution_radar/run", "POST", { date: dateStr });

    let done = false;
    for (let i = 0; i < 15; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const elapsed = (i + 1) * 2;
      if (indicator) indicator.textContent = `${elapsed}s`;
      try {
        const st = await api("/api/apps/execution_radar/status");
        if (!st.running) {
          done = true;
          if (st.error) {
            toast(t("er.runFailed") + ": " + st.error, "error");
          }
          break;
        }
      } catch (_) {}
    }

    btn.textContent = origText;
    btn.classList.remove("btn-loading");
    btn.disabled = false;
    if (indicator) { indicator.style.display = "none"; }

    await _refreshAllErPanels();

    if (done) {
      toast(t("er.runDone"), "success");
    } else {
      toast(t("er.runTimeout"), "warning");
    }
  } catch (e) {
    toast(t("er.runFailed") + ": " + e.message, "error");
    btn.textContent = origText;
    btn.classList.remove("btn-loading");
    btn.disabled = false;
    if (indicator) { indicator.style.display = "none"; }
  }
}

// ── Intent Engine Console ─────────────────────────────────────────────

// ── Intent Engine Visualization Dashboard ─────────────────────────
let _ieChartReduction = null;
let _ieChartGolden = null;
let _ieChartLlm = null;
let _ieChartLabelPie = null;
let _ieChartModePie = null;
let _ieChartDecisionPie = null;
let _ieChartRiskPie = null;
let _ieTimeRange = 7;

async function openIntentEngineDetail() {
  document.getElementById("app-detail-title").textContent = `🎯 ${t("ie.title")}`;
  switchPage("app-detail");
  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  let cfg = {};
  try { cfg = await api("/api/apps/intent_engine/config"); } catch(_) {}

  container.innerHTML = `
    <!-- 1. Health Overview -->
    <div class="app-detail-section ie-health-section">
      <div class="ie-section-header">
        <h3>${t("ie.healthOverview")}</h3>
        <div class="ie-time-range">
          <button class="btn btn-sm ${_ieTimeRange===7?'btn-primary':''}" onclick="ieSetRange(7)">${t("ie.last7d")}</button>
          <button class="btn btn-sm ${_ieTimeRange===14?'btn-primary':''}" onclick="ieSetRange(14)">${t("ie.last14d")}</button>
          <button class="btn btn-sm ${_ieTimeRange===30?'btn-primary':''}" onclick="ieSetRange(30)">${t("ie.last30d")}</button>
        </div>
      </div>
      <div id="ie-health-score" class="ie-health-score-box"></div>
      <div id="ie-metrics-cards" class="ie-metrics-grid"></div>
    </div>

    <!-- 2. Route Effectiveness -->
    <div class="app-detail-section">
      <h3>${t("ie.routeEffect")}</h3>
      <div class="ie-charts-row">
        <div class="ie-chart-box">
          <canvas id="ie-chart-reduction"></canvas>
        </div>
        <div class="ie-chart-box">
          <canvas id="ie-chart-golden"></canvas>
        </div>
        <div class="ie-chart-box">
          <canvas id="ie-chart-llm"></canvas>
        </div>
      </div>
    </div>

    <!-- 3. Pattern Distribution & Tool Analysis -->
    <div class="app-detail-section">
      <h3>${t("ie.patternDist")}</h3>
      <div class="ie-dist-row">
        <div class="ie-dist-chart-col">
          <h4>${t("ie.routeLabelDist")}</h4>
          <div class="ie-pie-wrap"><canvas id="ie-chart-labels"></canvas></div>
        </div>
        <div class="ie-dist-chart-col">
          <h4>${t("ie.routingMethod")}</h4>
          <div class="ie-pie-wrap"><canvas id="ie-chart-modes"></canvas></div>
        </div>
        <div class="ie-dist-chart-col">
          <h4>${t("ie.execPath")}</h4>
          <div class="ie-pie-wrap"><canvas id="ie-chart-decisions"></canvas></div>
        </div>
        <div class="ie-dist-chart-col">
          <h4>${t("ie.riskDist")}</h4>
          <div class="ie-pie-wrap"><canvas id="ie-chart-risk"></canvas></div>
        </div>
      </div>
      <div style="margin-top:16px;">
        <h4>${t("ie.toolPruneMap")}</h4>
        <div id="ie-tool-heatmap"></div>
      </div>
    </div>

    <!-- 3.5. Composite Intent Metrics -->
    <div class="app-detail-section">
      <details id="ie-composite-panel">
        <summary style="cursor:pointer;font-weight:600;font-size:15px;">
          \u{1F9E9} \u7EC4\u5408\u610F\u56FE\u76D1\u63A7
          <span style="font-size:11px;color:var(--subtext0);margin-left:8px;">Composite vs Single \u7EDF\u8BA1</span>
        </summary>
        <div id="ie-composite-metrics" style="margin-top:12px;"></div>
        <div id="ie-composite-test" style="margin-top:12px;">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;">
            <input type="text" id="ie-composite-input" class="form-input" placeholder="\u8F93\u5165\u6D4B\u8BD5\u6587\u672C\u2026" style="flex:1;font-size:13px;">
            <button class="btn btn-sm btn-primary" onclick="ieCompositeTest()">\u6D4B\u8BD5</button>
          </div>
          <div id="ie-composite-result" style="font-size:12px;"></div>
        </div>
      </details>
    </div>

    <!-- 4. Execution Detail -->
    <div class="app-detail-section">
      <details id="ie-detail-panel">
        <summary style="cursor:pointer;font-weight:600;font-size:15px;">${t("ie.execDetail")}</summary>
        <div id="ie-runs-table" style="margin-top:12px;"></div>
      </details>
    </div>

    <!-- 5. Advanced Config (collapsed by default) -->
    <div class="app-detail-section">
      <details id="ie-config-panel">
        <summary style="cursor:pointer;font-weight:600;font-size:13px;color:var(--subtext0)">Advanced</summary>
        <div style="margin-top:12px;">
          <div class="digest-config-grid" style="margin-bottom:16px;">
            <div class="form-group">
              <label>${t("ie.routeConfLow")}</label>
              <input type="number" id="ie-conf-low" value="${cfg.route_conf_low || 0.4}" step="0.05" min="0" max="1"
                     onchange="updateIeConfigAdvanced('route_conf_low', parseFloat(this.value))" class="form-input">
            </div>
          </div>
        </div>
      </details>
    </div>

    <!-- 6. Idle Learning -->
    <div class="app-detail-section">
      <details id="ie-learning-panel">
        <summary style="cursor:pointer;font-weight:600;font-size:15px;">
          ${t("ie.learning")}
          <span style="font-size:11px;color:var(--subtext0);margin-left:8px;">${t("ie.learningDesc")}</span>
        </summary>
        <div style="margin-top:16px;">

          <!-- 6a. Learning Config -->
          <div style="margin-bottom:20px;">
            <h4 style="margin-bottom:10px;">⚙️ ${t("ie.learningEnabled")}</h4>
            <div class="digest-config-grid" style="gap:12px;">
              <div class="form-group" style="display:flex;align-items:center;gap:8px;">
                <label style="min-width:100px;">${t("ie.learningEnabled")}</label>
                <input type="checkbox" id="ie-learn-enabled" onchange="ieLearningToggle('nightly_learning_enabled', this.checked)">
              </div>
              <div class="form-group" style="display:flex;align-items:center;gap:8px;">
                <label style="min-width:100px;">${t("ie.learningUseLlm")}</label>
                <input type="checkbox" id="ie-learn-usellm" onchange="ieLearningToggle('nightly_learning_use_llm', this.checked)">
              </div>
              <div class="form-group" style="display:flex;align-items:center;gap:8px;">
                <label style="min-width:100px;">${t("ie.learningSanitize")}</label>
                <input type="checkbox" id="ie-learn-sanitize" onchange="ieLearningToggle('nightly_learning_sanitize_pii', this.checked)">
              </div>
              <div class="form-group">
                <label>${t("ie.learningMaxSamples")}</label>
                <input type="number" id="ie-learn-maxsamples" min="10" max="1000" step="10" class="form-input"
                       onchange="ieLearningToggle('nightly_learning_max_samples', parseInt(this.value))">
              </div>
              <div class="form-group">
                <label>${t("ie.learningMinRuns")}</label>
                <input type="number" id="ie-learn-minruns" min="1" max="500" step="1" class="form-input"
                       onchange="ieLearningToggle('nightly_learning_min_runs', parseInt(this.value))">
              </div>
              <div class="form-group">
                <label>${t("ie.learningMinMisroutes")}</label>
                <input type="number" id="ie-learn-minmis" min="0" max="100" step="1" class="form-input"
                       onchange="ieLearningToggle('nightly_learning_min_misroutes', parseInt(this.value))">
              </div>
            </div>
            <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
              <button class="btn btn-sm btn-primary" onclick="ieLearningRun(false)" id="ie-learn-run-btn">${t("ie.learningRun")}</button>
              <button class="btn btn-sm" onclick="ieLearningRun(true)">${t("ie.learningDryRun")}</button>
              <div id="ie-learn-stats" style="font-size:11px;color:var(--subtext0);margin-left:8px;line-height:28px;"></div>
            </div>
          </div>

          <!-- 6b. User Lexicon -->
          <div style="margin-bottom:20px;">
            <h4 style="margin-bottom:10px;">📖 ${t("ie.lexicon")}</h4>
            <div style="display:flex;gap:8px;margin-bottom:8px;">
              <select id="ie-lex-version-sel" class="form-input" style="max-width:200px;font-size:12px;" onchange="ieLexiconLoadVersion(this.value)">
                <option value="current">${t("ie.lexiconCurrent")}</option>
              </select>
              <button class="btn btn-sm" onclick="ieLexiconRollback()">${t("ie.lexiconRollback")}</button>
            </div>
            <div id="ie-lexicon-content" style="font-size:12px;"></div>
          </div>

          <!-- 6c. Case Key Aliases -->
          <div style="margin-bottom:20px;">
            <h4 style="margin-bottom:10px;">🔗 ${t("ie.aliases")}</h4>
            <div id="ie-alias-list" style="font-size:12px;margin-bottom:8px;"></div>
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
              <input type="text" id="ie-alias-from" placeholder="${t("ie.aliasFrom")}" class="form-input" style="max-width:160px;font-size:12px;">
              <span style="color:var(--subtext0);">→</span>
              <input type="text" id="ie-alias-to" placeholder="${t("ie.aliasTo")}" class="form-input" style="max-width:160px;font-size:12px;">
              <button class="btn btn-sm" onclick="ieAliasAdd()">${t("ie.aliasAdd")}</button>
            </div>
          </div>

          <!-- 6d. Privacy -->
          <div style="margin-bottom:20px;">
            <h4 style="margin-bottom:10px;">🔒 ${t("ie.privacy")}</h4>
            <div id="ie-privacy-info" style="font-size:12px;"></div>
          </div>

          <!-- 6e. Audit Trail -->
          <div>
            <h4 style="margin-bottom:10px;">📋 ${t("ie.auditTrail")}</h4>
            <div id="ie-audit-list" style="font-size:12px;"></div>
          </div>

        </div>
      </details>
    </div>
  `;

  await _ieRefreshAll();
}

function ieSetRange(days) {
  _ieTimeRange = days;
  document.querySelectorAll(".ie-time-range .btn").forEach(b => b.classList.remove("btn-primary"));
  event.target.classList.add("btn-primary");
  _ieRefreshAll();
}

async function _ieRefreshAll() {
  await Promise.all([
    _ieLoadMetrics(),
    _ieLoadTrends(),
    _ieLoadDistribution(),
    _ieLoadRuns(),
    _ieLoadLearningPanel(),
    _ieLoadCompositeMetrics(),
  ]);
}

// ── Composite Intent Metrics ─────────────────────────────────────

async function _ieLoadCompositeMetrics() {
  const el = document.getElementById("ie-composite-metrics");
  if (!el) return;
  try {
    const d = await api("/api/ie/composite/metrics");
    if (!d || d.total_requests === 0) {
      el.innerHTML = '<div style="color:var(--subtext0);font-size:12px;">\u6682\u65E0\u7EC4\u5408\u610F\u56FE\u6570\u636E\uFF0C\u53D1\u9001\u6D88\u606F\u540E\u5C06\u81EA\u52A8\u7EDF\u8BA1</div>';
      return;
    }
    const cats = Object.entries(d.category_distribution || {}).sort((a,b) => b[1] - a[1]);
    const catHtml = cats.slice(0, 8).map(function(c) {
      const icon = _CATEGORY_ICONS[c[0]] || "\u{1F4A1}";
      return `<span class="cib-cat-chip">${icon} ${c[0]} <b>${c[1]}</b></span>`;
    }).join("");
    el.innerHTML = `
      <div class="ie-metrics-grid" style="margin-bottom:12px;">
        <div class="ie-metric-card">
          <div class="ie-metric-value">${d.total_requests}</div>
          <div class="ie-metric-label">\u603B\u8BF7\u6C42</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${d.single_count}</div>
          <div class="ie-metric-label">\u5355\u6B65\u4EFB\u52A1</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value" style="color:var(--lavender)">${d.composite_count}</div>
          <div class="ie-metric-label">\u7EC4\u5408\u4EFB\u52A1</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value" style="color:var(--mauve)">${d.composite_pct}%</div>
          <div class="ie-metric-label">\u7EC4\u5408\u5360\u6BD4</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${d.avg_intents_per_composite}</div>
          <div class="ie-metric-label">\u5E73\u5747\u6B65\u9AA4\u6570</div>
        </div>
      </div>
      <div style="margin-bottom:8px;">
        <span style="font-weight:600;font-size:12px;">\u610F\u56FE\u7C7B\u522B\u5206\u5E03</span>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">${catHtml || '<span style="color:var(--subtext0);font-size:11px;">-</span>'}</div>
      </div>
      ${d.recent && d.recent.length ? `
        <details style="margin-top:8px;">
          <summary style="cursor:pointer;font-size:12px;color:var(--subtext0);">\u6700\u8FD1 ${d.recent.length} \u6761\u8BB0\u5F55</summary>
          <div style="margin-top:6px;max-height:200px;overflow-y:auto;">
            <table style="width:100%;font-size:11px;border-collapse:collapse;">
              <tr style="color:var(--subtext0);"><th style="text-align:left;padding:2px 6px;">\u6A21\u5F0F</th><th>\u4E3B\u7C7B\u522B</th><th>\u6B65\u9AA4</th><th>\u7F6E\u4FE1\u5EA6</th></tr>
              ${d.recent.map(function(r) {
                return `<tr style="border-top:1px solid var(--surface0);">
                  <td style="padding:2px 6px;">${r.mode === "composite" ? "\u{1F9E9}" : "\u2022"} ${r.mode}</td>
                  <td style="text-align:center;">${r.primary}</td>
                  <td style="text-align:center;">${r.intents}</td>
                  <td style="text-align:center;">${(r.conf * 100).toFixed(0)}%</td>
                </tr>`;
              }).join("")}
            </table>
          </div>
        </details>
      ` : ""}
    `;
  } catch(e) {
    el.innerHTML = '<div style="color:var(--red);font-size:12px;">\u52A0\u8F7D\u5931\u8D25: ' + e.message + '</div>';
  }
}

async function ieCompositeTest() {
  const input = document.getElementById("ie-composite-input");
  const resultEl = document.getElementById("ie-composite-result");
  if (!input || !resultEl) return;
  const text = input.value.trim();
  if (!text) return;
  resultEl.innerHTML = '<span style="color:var(--subtext0);">\u5206\u6790\u4E2D\u2026</span>';
  try {
    const d = await api("/api/ie/predict", "POST", { text });
    if (d.mode === "single") {
      resultEl.innerHTML = `<div style="padding:6px 0;"><b>\u5355\u6B65\u6A21\u5F0F</b> \xB7 \u7C7B\u522B: <code>${d.primary_category}</code> \xB7 \u7F6E\u4FE1\u5EA6: ${(d.route_conf * 100).toFixed(0)}%</div>`;
    } else {
      let stepsHtml = d.intents.map(function(s, i) {
        const icon = _CATEGORY_ICONS[s.category] || "\u{1F4A1}";
        return `<div class="cib-step"><span class="cib-step-num">${i+1}</span><span class="cib-step-icon">${icon}</span><span class="cib-step-cat">${s.category}</span><span class="cib-step-text">${s.text}</span><span class="cib-step-conf">${(s.confidence*100).toFixed(0)}%</span></div>`;
      }).join("");
      let edgesHtml = d.edges.map(function(e) {
        return `<div class="cib-arrow">${e.type === "parallel" ? "\u2195 \u5E76\u884C" : "\u2193 \u987A\u5E8F"}</div>`;
      }).join("");
      resultEl.innerHTML = `<div style="padding:6px 0;"><b>\u{1F9E9} \u7EC4\u5408\u6A21\u5F0F</b> \xB7 ${d.intents.length} \u6B65 \xB7 \u4E3B\u7C7B\u522B: <code>${d.primary_category}</code></div><div class="composite-intent-badge" style="margin-top:4px;"><div class="cib-detail" style="display:block;">${stepsHtml}</div></div>`;
    }
    _ieLoadCompositeMetrics();
  } catch(e) {
    resultEl.innerHTML = '<span style="color:var(--red);">\u5206\u6790\u5931\u8D25: ' + e.message + '</span>';
  }
}

async function updateIeConfig(key, value) {
  try {
    await api("/api/apps/intent_engine/config", "POST", {[key]: value});
    toast(`${key} → ${value}`, "success");
  } catch(e) { toast("Config update failed: " + e.message, "error"); }
}

async function updateIeConfigAdvanced(key, value) {
  try {
    await api("/api/apps/intent_engine/config", "POST", {[key]: value});
    toast(`${key} → ${value}`, "success");
  } catch(e) { toast("Config update failed: " + e.message, "error"); }
}

// ── 0. Idle Learning Panel ───────────────────────────────────────

async function _ieLoadLearningPanel() {
  await Promise.all([
    _ieLoadLearningConfig(),
    _ieLoadLearningStats(),
    _ieLoadLexicon("current"),
    _ieLoadLexiconVersions(),
    _ieLoadAliases(),
    _ieLoadPrivacy(),
    _ieLoadAudit(),
  ]);
}

async function _ieLoadLearningConfig() {
  try {
    const cfg = await api("/api/apps/intent_engine/learning/config");
    const el = (id) => document.getElementById(id);
    if (el("ie-learn-enabled")) el("ie-learn-enabled").checked = !!cfg.enabled;
    if (el("ie-learn-usellm")) el("ie-learn-usellm").checked = !!cfg.use_llm;
    if (el("ie-learn-sanitize")) el("ie-learn-sanitize").checked = cfg.sanitize_pii !== false;
    if (el("ie-learn-maxsamples")) el("ie-learn-maxsamples").value = cfg.max_samples || 200;
    if (el("ie-learn-minruns")) el("ie-learn-minruns").value = cfg.min_runs || 20;
    if (el("ie-learn-minmis")) el("ie-learn-minmis").value = cfg.min_misroutes || 5;
  } catch(_) {}
}

async function _ieLoadLearningStats() {
  try {
    const st = await api("/api/apps/intent_engine/learning/stats");
    const el = document.getElementById("ie-learn-stats");
    if (!el) return;
    const triggerIcon = st.should_trigger ? "🟢" : "🔴";
    el.innerHTML = `${triggerIcon} ${st.trigger_reason || ""} (${t("ie.learnTriggerRuns")}: ${st.total_runs || 0}, ${t("ie.learnTriggerMisroutes")}: ${st.misroute_count || 0})`;
  } catch(_) {}
}

async function ieLearningToggle(key, value) {
  try {
    await api("/api/apps/intent_engine/learning/config", "POST", {[key]: value});
    toast(`${key} → ${value}`, "success");
  } catch(e) { toast(e.message, "error"); }
}

async function ieLearningRun(dryRun) {
  const btn = document.getElementById("ie-learn-run-btn");
  if (btn) { btn.disabled = true; btn.textContent = t("ie.learningRunning"); }
  try {
    const res = await api("/api/apps/intent_engine/learning/run", "POST", {
      dry_run: !!dryRun, force: !dryRun,
    });
    toast(res.status === "skipped" ? res.reason : t("ie.learningDone"), res.status === "skipped" ? "warning" : "success");
    if (!dryRun) {
      await _ieLoadLexicon("current");
      await _ieLoadLexiconVersions();
      await _ieLoadAliases();
      await _ieLoadAudit();
    }
  } catch(e) { toast(t("ie.learningFailed") + ": " + e.message, "error"); }
  finally { if (btn) { btn.disabled = false; btn.textContent = t("ie.learningRun"); } }
}

// ── Lexicon ──────────────────────────────────────────────────────

async function _ieLoadLexicon(version) {
  const el = document.getElementById("ie-lexicon-content");
  if (!el) return;
  try {
    const url = version === "current"
      ? "/api/apps/intent_engine/learning/lexicon/current"
      : `/api/apps/intent_engine/learning/lexicon/${version}`;
    const lex = await api(url);
    if (!lex.active && !lex.synonyms && !lex.verb_map) {
      el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.lexiconNoData")}</span>`;
      return;
    }
    const syn = lex.synonyms || {};
    const verb = lex.verb_map || {};
    const stop = lex.stop_phrases || [];
    el.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;">
        <div>
          <strong>${t("ie.lexiconSynonyms")}</strong> (${Object.keys(syn).length})
          <div style="max-height:180px;overflow-y:auto;margin-top:4px;border:1px solid var(--border);border-radius:6px;padding:6px;">
            ${Object.keys(syn).length ? Object.entries(syn).map(([k,v]) =>
              `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--border);">
                <code>${_escHtml(k)}</code><span style="color:var(--subtext0)">→</span><code>${_escHtml(v)}</code>
              </div>`).join("") : `<span style="color:var(--subtext0)">—</span>`}
          </div>
        </div>
        <div>
          <strong>${t("ie.lexiconVerbMap")}</strong> (${Object.keys(verb).length})
          <div style="max-height:180px;overflow-y:auto;margin-top:4px;border:1px solid var(--border);border-radius:6px;padding:6px;">
            ${Object.keys(verb).length ? Object.entries(verb).map(([k,v]) =>
              `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--border);">
                <code>${_escHtml(k)}</code><span style="color:var(--subtext0)">→</span><code>${_escHtml(v)}</code>
              </div>`).join("") : `<span style="color:var(--subtext0)">—</span>`}
          </div>
        </div>
        <div>
          <strong>${t("ie.lexiconStopPhrases")}</strong> (${stop.length})
          <div style="max-height:180px;overflow-y:auto;margin-top:4px;border:1px solid var(--border);border-radius:6px;padding:6px;">
            ${stop.length ? stop.map(s =>
              `<div style="padding:2px 0;border-bottom:1px solid var(--border);"><code>${_escHtml(s)}</code></div>`).join("") : `<span style="color:var(--subtext0)">—</span>`}
          </div>
        </div>
      </div>
      ${lex.version != null ? `<div style="margin-top:6px;color:var(--subtext0);font-size:11px;">v${lex.version} · ${lex.source || ""} · ${lex.created_at || ""}</div>` : ""}
    `;
  } catch(_) {
    el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.lexiconNoData")}</span>`;
  }
}

async function _ieLoadLexiconVersions() {
  const sel = document.getElementById("ie-lex-version-sel");
  if (!sel) return;
  try {
    const versions = await api("/api/apps/intent_engine/learning/lexicon/versions");
    const arr = Array.isArray(versions) ? versions : [];
    sel.innerHTML = `<option value="current">${t("ie.lexiconCurrent")}</option>` +
      arr.map(v => `<option value="${v.version}">v${v.version} (${v.source || ""} · ${(v.created_at||"").slice(0,16)})</option>`).join("");
  } catch(_) {}
}

function ieLexiconLoadVersion(val) {
  _ieLoadLexicon(val);
}

async function ieLexiconRollback() {
  const sel = document.getElementById("ie-lex-version-sel");
  if (!sel || sel.value === "current") { toast(t("ie.selectVersionFirst"), "warning"); return; }
  try {
    const res = await api("/api/apps/intent_engine/learning/lexicon/rollback", "POST", { version: parseInt(sel.value) });
    if (res.error) { toast(res.error, "error"); return; }
    toast(`${t("ie.rolledBackTo")} v${sel.value}`, "success");
    await _ieLoadLexicon("current");
    await _ieLoadLexiconVersions();
  } catch(e) { toast(e.message, "error"); }
}

// ── Case Key Aliases ─────────────────────────────────────────────

async function _ieLoadAliases() {
  const el = document.getElementById("ie-alias-list");
  if (!el) return;
  try {
    const aliases = await api("/api/apps/intent_engine/learning/aliases");
    const arr = Array.isArray(aliases) ? aliases : [];
    if (!arr.length) { el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.aliasNoData")}</span>`; return; }
    el.innerHTML = `<table style="width:100%;border-collapse:collapse;">
      <tr style="border-bottom:2px solid var(--border);text-align:left;">
        <th style="padding:4px 8px;">${t("ie.aliasFrom")}</th>
        <th style="padding:4px 8px;">${t("ie.aliasTo")}</th>
        <th style="padding:4px 8px;"></th>
      </tr>
      ${arr.map(a => `<tr style="border-bottom:1px solid var(--border);">
        <td style="padding:4px 8px;"><code>${_escHtml(a.alias)}</code></td>
        <td style="padding:4px 8px;"><code>${_escHtml(a.canonical)}</code></td>
        <td style="padding:4px 8px;"><button class="btn btn-sm" style="font-size:10px;padding:1px 6px;" onclick="ieAliasDelete('${_escHtml(a.alias)}')">✕</button></td>
      </tr>`).join("")}
    </table>`;
  } catch(_) {
    el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.aliasNoData")}</span>`;
  }
}

async function ieAliasAdd() {
  const from = document.getElementById("ie-alias-from");
  const to = document.getElementById("ie-alias-to");
  if (!from || !to || !from.value.trim() || !to.value.trim()) { toast(t("ie.fillBothFields"), "warning"); return; }
  try {
    await api("/api/apps/intent_engine/learning/aliases", "POST", {
      alias: from.value.trim(), canonical: to.value.trim(),
    });
    from.value = ""; to.value = "";
    toast(t("ie.aliasAdded"), "success");
    await _ieLoadAliases();
  } catch(e) { toast(e.message, "error"); }
}

async function ieAliasDelete(alias) {
  try {
    await api(`/api/apps/intent_engine/learning/aliases/${encodeURIComponent(alias)}`, "DELETE");
    toast(t("ie.aliasRemoved"), "success");
    await _ieLoadAliases();
  } catch(e) { toast(e.message, "error"); }
}

// ── Privacy Info ─────────────────────────────────────────────────

async function _ieLoadPrivacy() {
  const el = document.getElementById("ie-privacy-info");
  if (!el) return;
  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
      <div>
        <strong style="color:var(--green);">${t("ie.privacySentData")}</strong>
        <ul style="margin:4px 0;padding-left:16px;">
          <li>${t("ie.privacySent1")}</li>
          <li>${t("ie.privacySent2")}</li>
          <li>${t("ie.privacySent3")}</li>
          <li>${t("ie.privacySent4")}</li>
        </ul>
      </div>
      <div>
        <strong style="color:var(--red);">${t("ie.privacyNeverSent")}</strong>
        <ul style="margin:4px 0;padding-left:16px;">
          <li>${t("ie.privacyNever1")}</li>
          <li>${t("ie.privacyNever2")}</li>
          <li>${t("ie.privacyNever3")}</li>
          <li>${t("ie.privacyNever4")}</li>
        </ul>
      </div>
      <div>
        <strong style="color:var(--blue);">${t("ie.privacyLearned")}</strong>
        <ul style="margin:4px 0;padding-left:16px;">
          <li>${t("ie.privacyLearned1")}</li>
          <li>${t("ie.privacyLearned2")}</li>
          <li>${t("ie.privacyLearned3")}</li>
          <li>${t("ie.privacyLearned4")}</li>
        </ul>
      </div>
    </div>
    <div style="margin-top:8px;color:var(--subtext0);font-size:11px;">${t("ie.privacyStorage")}</div>
  `;
}

// ── Audit Trail ──────────────────────────────────────────────────

function _ieStatusText(status) {
  const map = {
    completed: "ie.statusCompleted",
    success: "ie.statusSuccess",
    running: "ie.statusRunning",
    skipped: "ie.statusSkipped",
    error: "ie.statusError",
    dry_run: "ie.statusDryRun",
    local_only: "ie.statusLocalOnly",
  };
  return t(map[status] || "ie.statusUnknown");
}

async function _ieLoadAudit() {
  const el = document.getElementById("ie-audit-list");
  if (!el) return;
  try {
    const runs = await api("/api/apps/intent_engine/learning/runs?limit=10");
    const arr = Array.isArray(runs) ? runs : [];
    if (!arr.length) { el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.auditNoRuns")}</span>`; return; }
    el.innerHTML = `<table style="width:100%;border-collapse:collapse;">
      <tr style="border-bottom:2px solid var(--border);text-align:left;font-size:11px;">
        <th style="padding:4px 6px;">${t("ie.auditDate")}</th>
        <th style="padding:4px 6px;">${t("ie.auditStatus")}</th>
        <th style="padding:4px 6px;">${t("ie.auditStartTime")}</th>
        <th style="padding:4px 6px;">${t("ie.auditTokens")}</th>
        <th style="padding:4px 6px;">${t("ie.auditArtifactsSummary")}</th>
        <th style="padding:4px 6px;"></th>
      </tr>
      ${arr.map(r => {
        const st = r.status || "unknown";
        const color = st === "completed" || st === "success" ? "var(--green)" : st === "error" ? "var(--red)" : "var(--subtext0)";
        let startTime = "—";
        if (r.created_at) {
          try {
            const d = new Date(r.created_at);
            startTime = d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});
          } catch(e) { startTime = "—"; }
        }
        return `<tr style="border-bottom:1px solid var(--border);font-size:11px;">
          <td style="padding:4px 6px;">${_escHtml((r.run_date || r.created_at || "").slice(0,10))}</td>
          <td style="padding:4px 6px;color:${color};">${_ieStatusText(st)}</td>
          <td style="padding:4px 6px;">${startTime}</td>
          <td style="padding:4px 6px;">${r.token_cost || "—"}</td>
          <td style="padding:4px 6px;">${_escHtml(r.artifacts_summary || "—")}</td>
          <td style="padding:4px 6px;"><button class="btn btn-sm" style="font-size:10px;padding:1px 6px;" onclick="ieAuditDetail('${_escHtml(r.id || r.run_id || "")}')">${t("ie.auditDetail")}</button></td>
        </tr>`;
      }).join("")}
    </table>`;
  } catch(_) {
    el.innerHTML = `<span style="color:var(--subtext0)">${t("ie.auditNoRuns")}</span>`;
  }
}

async function ieAuditDetail(runId) {
  if (!runId) return;
  try {
    const d = await api(`/api/apps/intent_engine/learning/runs/${encodeURIComponent(runId)}`);
    const inputStats = d.input_stats_json || {};
    const outputArtifacts = d.output_artifacts_json || {};
    const promptSent = inputStats.prompt_sent || d.prompt_sent || "";
    const llmRaw = inputStats.llm_response_raw || d.llm_response_raw || "";
    const preStyle = "max-height:240px;overflow:auto;background:var(--bg-base);padding:10px;border-radius:6px;font-size:11px;white-space:pre-wrap;user-select:text;cursor:text;border:1px solid var(--border);";

    const parts = [];
    if (promptSent) parts.push(`<div><strong>${t("ie.auditPromptSent")}</strong><pre style="${preStyle}">${_escHtml(typeof promptSent === "string" ? promptSent : JSON.stringify(promptSent, null, 2))}</pre></div>`);
    if (llmRaw) parts.push(`<div><strong>${t("ie.auditLlmResponse")}</strong><pre style="${preStyle}">${_escHtml(typeof llmRaw === "string" ? llmRaw : JSON.stringify(llmRaw, null, 2))}</pre></div>`);
    if (outputArtifacts && Object.keys(outputArtifacts).length) parts.push(`<div><strong>${t("ie.auditArtifacts")}</strong><pre style="${preStyle}">${_escHtml(JSON.stringify(outputArtifacts, null, 2))}</pre></div>`);
    if (!parts.length) parts.push(`<pre style="${preStyle}">${_escHtml(JSON.stringify(d, null, 2))}</pre>`);

    let duration = "—";
    if (d.created_at && d.completed_at) {
      const ms = new Date(d.completed_at).getTime() - new Date(d.created_at).getTime();
      if (ms > 0) duration = ms < 1000 ? ms + "ms" : (ms / 1000).toFixed(1) + "s";
    }

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;";
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    const statusOk = d.status === "completed" || d.status === "success";
    const statusText = _ieStatusText(d.status);
    overlay.innerHTML = `<div style="background:var(--bg-surface);border-radius:12px;padding:24px;max-width:720px;width:92%;max-height:85vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3);border:1px solid var(--border);user-select:text;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h4 style="margin:0;">${t("ie.auditTrail")} — ${_escHtml((d.run_date || d.target_date || "").slice(0,10))}</h4>
        <button class="btn btn-sm" onclick="this.closest('div[style*=fixed]').remove()">✕</button>
      </div>
      <div style="font-size:12px;color:var(--subtext0);margin-bottom:14px;display:flex;flex-wrap:wrap;gap:12px;">
        <span>${t("ie.auditStatus")}: <strong style="color:${statusOk?'var(--green)':'var(--red)'}">${statusText}</strong></span>
        <span>${t("ie.auditModel")}: ${_escHtml(d.model_used||"—")}</span>
        <span>${t("ie.auditTokens")}: ${d.token_cost||"—"}</span>
        <span>${t("ie.auditDuration")}: ${duration}</span>
      </div>
      ${parts.join("<div style='height:14px;'></div>")}
      ${d.error_log ? `<div style="margin-top:14px;"><strong style="color:var(--red);">Error</strong><pre style="${preStyle};color:var(--red);">${_escHtml(d.error_log)}</pre></div>` : ""}
    </div>`;
    document.body.appendChild(overlay);
  } catch(e) { toast(e.message, "error"); }
}

// ── 1. Health Metrics ────────────────────────────────────────────

async function _ieLoadMetrics() {
  try {
    const [m, mis] = await Promise.all([
      api(`/api/apps/intent_engine/metrics?days=${_ieTimeRange}`),
      api(`/api/apps/intent_engine/misroutes?days=${_ieTimeRange}`),
    ]);

    const scoreEl = document.getElementById("ie-health-score");
    if (scoreEl) {
      const score = m.routing_health_score || 0;
      let level, color;
      if (score >= 70) { level = t("ie.good"); color = "#10b981"; }
      else if (score >= 40) { level = t("ie.fair"); color = "#f59e0b"; }
      else { level = t("ie.poor"); color = "#ef4444"; }
      scoreEl.innerHTML = `
        <div class="ie-score-ring" style="--score-color:${color}">
          <svg viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="var(--bg-surface0)" stroke-width="8"/>
            <circle cx="50" cy="50" r="42" fill="none" stroke="${color}" stroke-width="8"
                    stroke-dasharray="${score * 2.64} 264" stroke-dashoffset="0"
                    stroke-linecap="round" transform="rotate(-90 50 50)"/>
          </svg>
          <div class="ie-score-text">
            <span class="ie-score-num" style="color:${color}">${score}</span>
            <span class="ie-score-label">${level}</span>
          </div>
        </div>
        <div class="ie-score-title">${t("ie.routingHealth")}</div>
      `;
    }

    const cardsEl = document.getElementById("ie-metrics-cards");
    if (cardsEl) {
      const misRate = mis.suspected_rate || 0;
      cardsEl.innerHTML = `
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.total_runs || 0}</div>
          <div class="ie-metric-label">${t("ie.totalRuns")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.avg_tool_reduction || 0}%</div>
          <div class="ie-metric-label">${t("ie.avgToolReduction")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.golden_hit_rate || 0}%</div>
          <div class="ie-metric-label">${t("ie.goldenHitRate")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.avg_llm_calls || 0}</div>
          <div class="ie-metric-label">${t("ie.avgLlmCalls")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.avg_latency_ms || 0}ms</div>
          <div class="ie-metric-label">${t("ie.avgLatency")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.success_rate || 0}%</div>
          <div class="ie-metric-label">${t("ie.successRate")}</div>
        </div>
        <div class="ie-metric-card ${misRate > 10 ? 'ie-metric-warn' : ''}">
          <div class="ie-metric-value">${misRate}%</div>
          <div class="ie-metric-label">${t("ie.misrouteRate")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.reuse_count || 0} <small style="font-size:11px;color:var(--subtext0)">(${m.reuse_rate || 0}%)</small></div>
          <div class="ie-metric-label">${t("ie.reuseCount")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.fallback_rate || 0}%</div>
          <div class="ie-metric-label">${t("ie.fallbackRate")}</div>
        </div>
        <div class="ie-metric-card">
          <div class="ie-metric-value">${m.misroute_count || 0}</div>
          <div class="ie-metric-label">${t("ie.misrouteCount")}</div>
        </div>
      `;
    }
  } catch(e) { console.warn("ie metrics", e); }
}

// ── 2. Trend Charts ──────────────────────────────────────────────

async function _ieLoadTrends() {
  try {
    const d = await api(`/api/apps/intent_engine/trends?days=${_ieTimeRange}`);
    const labels = (d.dates || []).map(s => s.slice(5));
    const chartOpts = (title, maxY, suffix) => ({
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: title, font: { size: 12, weight: "500" }, color: "var(--text-secondary)" },
      },
      scales: {
        y: { beginAtZero: true, max: maxY || undefined, ticks: { callback: v => v + (suffix||""), font: { size: 10 } } },
        x: { ticks: { font: { size: 10 } } },
      },
    });

    const c1 = document.getElementById("ie-chart-reduction");
    if (c1) {
      if (_ieChartReduction) _ieChartReduction.destroy();
      _ieChartReduction = new Chart(c1, {
        type: "line",
        data: { labels, datasets: [{
          label: t("ie.avgToolReduction"),
          data: d.tool_reduction_rates || [],
          borderColor: "#6366f1", backgroundColor: "rgba(99,102,241,0.08)",
          fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2,
        }] },
        options: chartOpts(t("ie.toolReductionTrend"), 100, "%"),
      });
    }

    const c2 = document.getElementById("ie-chart-golden");
    if (c2) {
      if (_ieChartGolden) _ieChartGolden.destroy();
      _ieChartGolden = new Chart(c2, {
        type: "line",
        data: { labels, datasets: [{
          label: t("ie.goldenHitRate"),
          data: d.golden_hit_rates || [],
          borderColor: "#10b981", backgroundColor: "rgba(16,185,129,0.08)",
          fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2,
        }] },
        options: chartOpts(t("ie.goldenHitTrend"), 100, "%"),
      });
    }

    const c3 = document.getElementById("ie-chart-llm");
    if (c3) {
      if (_ieChartLlm) _ieChartLlm.destroy();
      _ieChartLlm = new Chart(c3, {
        type: "line",
        data: { labels, datasets: [{
          label: t("ie.avgLlmCalls"),
          data: d.llm_calls || [],
          borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.08)",
          fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2,
        }] },
        options: chartOpts(t("ie.llmCallTrend"), null, ""),
      });
    }
  } catch(e) { console.warn("ie trends", e); }
}

// ── 3. Distribution & Tool Heatmap ───────────────────────────────

async function _ieLoadDistribution() {
  try {
    const d = await api(`/api/apps/intent_engine/distribution?days=${_ieTimeRange}`);

    const PIE_COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6","#64748b"];

    const labelData = d.route_labels || {};
    const labelNames = Object.keys(labelData);
    const labelCounts = Object.values(labelData);
    const c1 = document.getElementById("ie-chart-labels");
    if (c1) {
      if (_ieChartLabelPie) _ieChartLabelPie.destroy();
      _ieChartLabelPie = new Chart(c1, {
        type: "doughnut",
        data: {
          labels: labelNames,
          datasets: [{ data: labelCounts, backgroundColor: PIE_COLORS.slice(0, labelNames.length), borderWidth: 0 }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "right", labels: { boxWidth: 10, padding: 8, font: { size: 11 } } } },
          cutout: "55%",
        },
      });
    }

    const _PIE_OPTS = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { boxWidth: 10, padding: 8, font: { size: 11 } } } },
      cutout: "55%",
    };

    const _EXEC_PATH_LABELS = {
      "llm_loop": "LLM 循环", "plan_reuse": "计划复用",
      "plan_reuse:golden": "Golden 复用", "plan_reuse:candidate": "候选复用",
      "plan_reuse:cached": "缓存复用", "blocked:cost": "成本阻止",
      "deterministic": "确定性",
    };
    const _RISK_COLORS = {"low": "#10b981", "medium": "#f59e0b", "high": "#ef4444"};

    const modeData = d.routing_methods || d.decision_modes || {};
    const modeNames = Object.keys(modeData);
    const modeCounts = Object.values(modeData);
    const c2 = document.getElementById("ie-chart-modes");
    if (c2) {
      if (_ieChartModePie) _ieChartModePie.destroy();
      _ieChartModePie = new Chart(c2, {
        type: "doughnut",
        data: {
          labels: modeNames,
          datasets: [{ data: modeCounts, backgroundColor: PIE_COLORS.slice(0, modeNames.length), borderWidth: 0 }],
        },
        options: _PIE_OPTS,
      });
    }

    const pathData = d.execution_paths || d.decisions || {};
    const pathNames = Object.keys(pathData).map(k => _EXEC_PATH_LABELS[k] || k);
    const pathCounts = Object.values(pathData);
    const c3 = document.getElementById("ie-chart-decisions");
    if (c3) {
      if (_ieChartDecisionPie) _ieChartDecisionPie.destroy();
      _ieChartDecisionPie = new Chart(c3, {
        type: "doughnut",
        data: {
          labels: pathNames,
          datasets: [{ data: pathCounts, backgroundColor: PIE_COLORS.slice(0, pathNames.length), borderWidth: 0 }],
        },
        options: _PIE_OPTS,
      });
    }

    const riskData = d.risk_levels || {};
    const riskNames = Object.keys(riskData);
    const riskCounts = Object.values(riskData);
    const c4 = document.getElementById("ie-chart-risk");
    if (c4) {
      if (_ieChartRiskPie) _ieChartRiskPie.destroy();
      _ieChartRiskPie = new Chart(c4, {
        type: "doughnut",
        data: {
          labels: riskNames,
          datasets: [{ data: riskCounts, backgroundColor: riskNames.map(r => _RISK_COLORS[r] || "#64748b"), borderWidth: 0 }],
        },
        options: _PIE_OPTS,
      });
    }

    const heatEl = document.getElementById("ie-tool-heatmap");
    if (heatEl) {
      const tools = d.tool_analysis || [];
      if (!tools.length) {
        heatEl.innerHTML = `<p style="color:var(--text-secondary)">暂无数据</p>`;
      } else {
        const maxKept = Math.max(...tools.map(t => t.kept_count), 1);
        heatEl.innerHTML = `
          <div class="ie-heatmap-table">
            <div class="ie-heatmap-header">
              <span>${t("ie.tool")}</span>
              <span>${t("ie.keptCount")}</span>
              <span>${t("ie.prunedCount")}</span>
              <span>${t("ie.keptRate")}</span>
              <span></span>
            </div>
            ${tools.slice(0, 20).map(tool => {
              const barW = Math.round(tool.kept_count / maxKept * 100);
              const hue = Math.round(tool.kept_rate * 1.2);
              return `<div class="ie-heatmap-row">
                <span class="ie-heatmap-tool" title="${tool.tool}">${tool.tool}</span>
                <span>${tool.kept_count}</span>
                <span>${tool.pruned_count}</span>
                <span>${tool.kept_rate}%</span>
                <span class="ie-heatmap-bar-cell">
                  <div class="ie-heatmap-bar" style="width:${barW}%;background:hsl(${hue},70%,50%)"></div>
                </span>
              </div>`;
            }).join("")}
          </div>
        `;
      }
    }
  } catch(e) { console.warn("ie dist", e); }
}

// ── 4. Execution Detail ──────────────────────────────────────────

async function _ieLoadRuns() {
  const el = document.getElementById("ie-runs-table");
  if (!el) return;
  try {
    const runs = await api(`/api/apps/intent_engine/runs?limit=50`);
    if (!runs || !runs.length) {
      el.innerHTML = `<p style="color:var(--text-secondary)">${t("ie.noRuns")}</p>`;
      return;
    }
    el.innerHTML = `
      <table class="er-task-table ie-detail-table">
        <thead><tr>
          <th></th>
          <th>${t("ie.time")}</th>
          <th>${t("ie.text")}</th>
          <th>${t("ie.routeLabels")}</th>
          <th>${t("ie.intentConfidence")}</th>
          <th>${t("ie.reductionRate")}</th>
          <th>${t("ie.goldenHit")}</th>
          <th>${t("ie.planSource")}</th>
          <th>${t("ie.effectiveSteps")}</th>
          <th>${t("ie.llmCalls")}</th>
          <th>${t("ie.costScore")}</th>
          <th>${t("ie.outcome")}</th>
        </tr></thead>
        <tbody>${runs.map((r, i) => {
          const reduction = r.tools_before > 0
            ? Math.round((r.tools_before - r.tools_after) / r.tools_before * 100) : 0;
          const golden = r.golden_hit || (r.plan_source && ["golden_v2_instance","golden_v2_template","golden_replay","golden_candidate"].includes(r.plan_source));
          const toolGroup = (() => { try { return JSON.parse(r.tool_group || "[]"); } catch(_) { return []; } })();
          const confidence = r.route_conf != null ? (r.route_conf * 100).toFixed(0) + '%' : '-';
          const effectiveSteps = r.effective_steps ?? '-';
          const totalTokens = r.total_tokens || 0;
          const planSource = r.plan_source || (r.decision === 'reuse_plan' ? 'reuse_plan' : (r.llm_attempts > 0 ? 'llm' : (r.decision_mode || '-')));
          return `
            <tr class="ie-run-row" onclick="ieToggleDetail(${i})">
              <td><span class="ie-expand-icon" id="ie-expand-${i}">▶</span></td>
              <td style="white-space:nowrap">${(r.created_at || "").slice(5,16).replace("T"," ")}</td>
              <td class="ie-text-cell" title="${(r.user_text||"").replace(/"/g,"&quot;")}">${(r.user_text||"").slice(0,35)}</td>
              <td><code class="ie-label-tag">${r.final_category || r.route_label || "default"}</code>${r.user_corrected ? '<span style="color:var(--accent);font-size:9px;margin-left:4px;">✓</span>' : ''}</td>
              <td>${confidence}</td>
              <td>${r.tools_before}→${r.tools_after} <span class="ie-pct">(${reduction}%)</span></td>
              <td>${golden ? '<span class="ie-golden-yes">●</span>' : '<span class="ie-golden-no">○</span>'}</td>
              <td>${planSource}</td>
              <td>${effectiveSteps}</td>
              <td>${r.llm_attempts ?? "-"}</td>
              <td>${totalTokens}</td>
              <td>${_ieOutcomeBadge(r.outcome)}</td>
            </tr>
            <tr class="ie-detail-row" id="ie-detail-${i}" style="display:none">
              <td colspan="12">
                <div class="ie-detail-content">
                  <div class="ie-detail-row-main">
                    <div><strong>${t("ie.caseKey")}:</strong> ${r.case_key || "-"}</div>
                    <div><strong>${t("ie.latency")}:</strong> ${r.latency_ms ? r.latency_ms.toFixed(1) + 'ms' : '-'} | <strong>${t("ie.routingMethod")}:</strong> ${r.routing_method || r.decision_mode || "rule"} | <strong>${t("ie.execPath")}:</strong> ${r.execution_path || r.decision || "llm_loop"} | <strong>Risk:</strong> <span class="ie-risk-${r.risk_level || 'low'}">${r.risk_level || "low"}</span>${r.misroute_suspect ? ' ⚠️' : ''}</div>
                    <div><strong>${t("ie.allowedTools")}:</strong>
                      <span class="ie-tool-chips">${toolGroup.length ? toolGroup.map(t => `<code class="ie-tool-chip">${t}</code>`).join("") : "-"}</span>
                    </div>
                  </div>
                  <div class="ie-detail-row-correct" style="margin-top:8px;display:flex;align-items:center;gap:8px;">
                    <strong style="font-size:11px;">${t("ie.correctCategory")}:</strong>
                    <select id="ie-correct-sel-${i}" style="font-size:11px;padding:2px 6px;border-radius:4px;border:1px solid var(--border);background:var(--bg-base);color:var(--text);">
                      <option value="">--</option>
                      ${["search","fs","browser","net","system","schedule","comm","general","chat"].map(c =>
                        `<option value="${c}" ${((r.final_category || r.route_label)||"").startsWith(c) ? 'selected' : ''}>${c}</option>`
                      ).join("")}
                    </select>
                    <button onclick="ieCorrectCategory('${r.id}', ${i})" style="font-size:11px;padding:2px 10px;border-radius:4px;cursor:pointer;background:var(--accent);color:#fff;border:none;">${t("ie.submitCorrection")}</button>
                    ${r.user_corrected ? `<span style="color:var(--accent);font-size:10px;">✓ ${t("ie.alreadyCorrected")}</span>` : ''}
                  </div>
                  <div style="margin-top:6px;display:flex;gap:12px;font-size:10px;color:var(--subtext0);">
                    <span><strong>rule_conf:</strong> ${r.rule_conf != null ? r.rule_conf.toFixed(3) : '-'}</span>
                    <span><strong>case_conf:</strong> ${r.case_conf != null ? r.case_conf.toFixed(3) : '-'}</span>
                    <span><strong>llm_conf:</strong> ${r.llm_conf != null ? r.llm_conf.toFixed(3) : '-'}</span>
                    <span><strong>source:</strong> ${r.confidence_source || '-'}</span>
                    <span><strong>arbiter:</strong> ${r.arbiter_reason || '-'}</span>
                  </div>
                  <details class="ie-raw-data" style="margin-top:8px;">
                    <summary style="cursor:pointer;font-size:10px;color:var(--subtext0)">🔍 原始数据</summary>
                    <pre style="margin-top:4px;padding:8px;background:var(--bg-base);border-radius:4px;font-size:10px;overflow-x:auto;">${JSON.stringify(r, null, 2)}</pre>
                  </details>
                </div>
              </td>
            </tr>`;
        }).join("")}</tbody>
      </table>
    `;
  } catch(e) { el.innerHTML = `<p style="color:var(--text-secondary)">加载失败</p>`; }
}

function ieToggleDetail(idx) {
  const row = document.getElementById(`ie-detail-${idx}`);
  const icon = document.getElementById(`ie-expand-${idx}`);
  if (!row) return;
  const show = row.style.display === "none";
  row.style.display = show ? "table-row" : "none";
  if (icon) icon.textContent = show ? "▼" : "▶";
}

async function ieCorrectCategory(runId, rowIdx) {
  const sel = document.getElementById(`ie-correct-sel-${rowIdx}`);
  if (!sel || !sel.value) { toast("请选择类别", "warning"); return; }
  try {
    const res = await api("/api/apps/intent_engine/correct", "POST", {
      run_id: runId,
      corrected_category: sel.value,
    });
    if (res.status === "ok") {
      toast(t("ie.correctionSaved"), "success");
      _ieLoadRuns();
    } else {
      toast(res.error || "correction failed", "error");
    }
  } catch(e) { toast("Correction failed: " + e.message, "error"); }
}

function _ieOutcomeBadge(outcome) {
  if (outcome === "success") return '<span class="ie-badge-ok">✓</span>';
  if (outcome === "fail") return '<span class="ie-badge-fail">✗</span>';
  return '<span class="ie-badge-none">-</span>';
}

// ── 5. Models ────────────────────────────────────────────────────


// ── End Intent Engine Visualization Dashboard ─────────────────────

// ── Strategy Hub Detail Page ──────────────────────────────────────────

async function openStrategyHubDetail() {
  document.getElementById("app-detail-title").textContent = `🧠 ${t("sh.title")}`;
  switchPage("app-detail");

  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("status.loading")}</div>`;

  container.innerHTML = `
    <div class="er-section">
      <h2>${t("sh.healthOverview")}</h2>
      <div class="er-health-bar" id="sh-health-bar" style="margin-bottom:16px;">
        <span class="er-health-label">${t("sh.healthLabel")}</span>
        <span class="er-health-score" id="sh-health-score">--</span>
      </div>
      <div class="er-kpi-grid" style="grid-template-columns:repeat(3,1fr);">
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-template-count">--</div>
          <div class="er-kpi-label">${t("sh.templates")}</div>
        </div>
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-instance-count">--</div>
          <div class="er-kpi-label">${t("sh.instances")}</div>
        </div>
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-candidate-count">--</div>
          <div class="er-kpi-label">${t("sh.candidates")}</div>
        </div>
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-hit-rate">--</div>
          <div class="er-kpi-label">${t("sh.hitRate")}</div>
        </div>
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-fail-rate">--</div>
          <div class="er-kpi-label">${t("sh.failRate")}</div>
        </div>
        <div class="er-kpi-card">
          <div class="er-kpi-value" id="sh-avg-replay">--</div>
          <div class="er-kpi-label">${t("sh.avgReplayTime")}</div>
        </div>
      </div>
    </div>

    <div class="er-section" id="sh-suggestions-section" style="display:none;">
      <h2>${t("sh.suggestions")}</h2>
      <div id="sh-suggestions-list" class="er-table-placeholder"></div>
    </div>

    <div class="er-section">
      <div class="er-tabs">
        <button class="er-tab active" data-shtab="templates" onclick="_shSwitchTab('templates')">${t("sh.templates")}</button>
        <button class="er-tab" data-shtab="instances" onclick="_shSwitchTab('instances')">${t("sh.instances")}</button>
        <button class="er-tab" data-shtab="candidates" onclick="_shSwitchTab('candidates')">${t("sh.candidates")}</button>
      </div>

      <div class="er-tab-pane" id="sh-tab-templates" style="display:block;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
          <div style="font-size:0.9rem;color:var(--text-sub);">${t("sh.templatesDesc")}</div>
          <button class="btn btn-primary btn-sm" onclick="_shGenerateTemplates()" style="white-space:nowrap;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><path d="M12 5v14M5 12h14"/></svg>
            ${t("sh.generateTemplates")}
          </button>
        </div>
        <div id="sh-templates-list" class="er-table-placeholder">${t("sh.loading")}</div>
      </div>
      <div class="er-tab-pane" id="sh-tab-instances" style="display:none;">
        <div id="sh-instances-list" class="er-table-placeholder">${t("sh.loading")}</div>
      </div>
      <div class="er-tab-pane" id="sh-tab-candidates" style="display:none;">
        <div id="sh-candidates-list" class="er-table-placeholder">${t("sh.loading")}</div>
      </div>
    </div>

    <div class="er-section" id="sh-detail-panel" style="display:none;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
        <button class="btn btn-sm" onclick="_shCloseDetail()">${t("sh.back")}</button>
        <h2 id="sh-detail-title" style="margin:0;"></h2>
      </div>
      <div id="sh-detail-content"></div>
    </div>
  `;

  await _shLoadMetrics();
  await _shLoadSuggestions();
  _shLoadTemplates();
  _shLoadInstances();
  _shLoadCandidates();
}

function _shSwitchTab(tab) {
  document.querySelectorAll("[data-shtab]").forEach(btn => btn.classList.toggle("active", btn.dataset.shtab === tab));
  ["templates", "instances", "candidates"].forEach(t => {
    const pane = document.getElementById(`sh-tab-${t}`);
    if (pane) pane.style.display = t === tab ? "block" : "none";
  });
}

async function _shLoadMetrics() {
  try {
    const d = await api("/api/apps/strategy_hub/metrics");
    const _v = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    _v("sh-template-count", d.template_count || 0);
    _v("sh-instance-count", d.instance_count || 0);
    _v("sh-candidate-count", d.candidate_count || 0);
    _v("sh-hit-rate", (d.hit_rate || 0) + "%");
    _v("sh-fail-rate", (d.fail_rate || 0) + "%");
    _v("sh-avg-replay", d.avg_replay_ms != null ? d.avg_replay_ms + "ms" : "--");

    const score = d.health_score || 0;
    const labelMap = { Healthy: t("sh.healthHealthy"), Stable: t("sh.healthStable"), Degraded: t("sh.healthDegraded"), Critical: t("sh.healthCritical") };
    const label = labelMap[d.health_label] || d.health_label || "—";
    const scoreEl = document.getElementById("sh-health-score");
    if (scoreEl) {
      scoreEl.textContent = `${score}/100 (${label})`;
      scoreEl.style.color = score >= 80 ? "var(--success)" : score >= 60 ? "var(--warning, #f59e0b)" : "var(--danger, #ef4444)";
    }
  } catch (e) { console.warn("sh metrics", e); }
}

async function _shLoadSuggestions() {
  try {
    const d = await api("/api/apps/strategy_hub/suggestions");
    const section = document.getElementById("sh-suggestions-section");
    const list = document.getElementById("sh-suggestions-list");
    if (!d.suggestions || !d.suggestions.length) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";
    list.innerHTML = d.suggestions.map(s =>
      `<div class="er-candidate-card" style="margin-bottom:8px;padding:10px 14px;">
        <span style="font-weight:600;">${_escHtml(s.intent_label)}</span>
        <span style="color:var(--text-secondary);margin-left:8px;">${s.instance_count} ${t("sh.suggestAbstract")}</span>
      </div>`
    ).join("");
  } catch(e) { console.warn("sh suggestions", e); }
}

async function _shLoadTemplates() {
  const el = document.getElementById("sh-templates-list");
  try {
    const d = await api("/api/apps/strategy_hub/templates?limit=50");
    if (!d.templates || !d.templates.length) {
      el.innerHTML = `<div class="er-table-placeholder">${t("sh.noTemplates")}</div>`;
      return;
    }
    el.innerHTML = `<table class="er-table"><thead><tr>
      <th>${t("sh.colTemplateId")}</th><th>${t("sh.colIntent")}</th><th>${t("sh.colVersion")}</th><th>${t("sh.colUseCount")}</th><th>${t("sh.colSuccessRate")}</th><th>${t("sh.colLastUsed")}</th><th>${t("sh.colStatus")}</th><th>${t("sh.colActions")}</th>
    </tr></thead><tbody>${d.templates.map(r => `<tr class="${r.status === 'stale' ? 'er-row-warn' : ''}">
      <td><a href="#" onclick="_shShowTemplateDetail('${_escHtml(r.template_id)}');return false;" class="er-link">${_escHtml(r.template_id.substring(0, 12))}…</a></td>
      <td>${_escHtml(r.intent_label)}</td>
      <td>v${r.version}</td>
      <td>${r.use_count}</td>
      <td>${r.success_rate}%</td>
      <td>${r.last_used_at ? r.last_used_at.substring(0, 10) : '--'}</td>
      <td><span class="er-badge ${r.status === 'stale' ? 'er-badge-warn' : 'er-badge-ok'}">${r.status}</span></td>
      <td><button class="btn btn-sm btn-danger" onclick="_shDeleteTemplate('${_escHtml(r.template_id)}')">${t("sh.delete")}</button></td>
    </tr>`).join("")}</tbody></table>`;
  } catch(e) { el.innerHTML = `<div class="er-table-placeholder">${t("sh.loadFailed")}</div>`; }
}

async function _shLoadInstances() {
  const el = document.getElementById("sh-instances-list");
  try {
    const d = await api("/api/apps/strategy_hub/instances?limit=50");
    if (!d.instances || !d.instances.length) {
      el.innerHTML = `<div class="er-table-placeholder">${t("sh.noInstances")}</div>`;
      return;
    }
    el.innerHTML = `<table class="er-table"><thead><tr>
      <th>${t("sh.colCaseKey")}</th><th>${t("sh.colTemplate")}</th><th>${t("sh.colIntent")}</th><th>${t("sh.colUseCount")}</th><th>${t("sh.colSuccessRate")}</th><th>${t("sh.colLastUsed")}</th><th>${t("sh.colStatus")}</th><th>${t("sh.colActions")}</th>
    </tr></thead><tbody>${d.instances.map(i => `<tr class="${i.status === 'stale' ? 'er-row-warn' : ''}">
      <td><a href="#" onclick="_shShowInstanceDetail('${_escHtml(i.case_key)}');return false;" class="er-link">${_escHtml(i.case_key.substring(0, 12))}…</a></td>
      <td>${i.template_id ? _escHtml(i.template_id.substring(0, 8)) + '…' : '--'}</td>
      <td>${_escHtml(i.intent_label || '--')}</td>
      <td>${i.use_count}</td>
      <td>${i.success_rate}%</td>
      <td>${i.last_used_at ? i.last_used_at.substring(0, 10) : '--'}</td>
      <td><span class="er-badge ${i.status === 'stale' ? 'er-badge-warn' : 'er-badge-ok'}">${i.status}</span></td>
      <td>
        <button class="btn btn-sm" onclick="_shInvalidateInstance('${_escHtml(i.case_key)}')">${t("sh.invalidate")}</button>
        <button class="btn btn-sm btn-danger" onclick="_shDeleteInstance('${_escHtml(i.case_key)}')">${t("sh.delete")}</button>
      </td>
    </tr>`).join("")}</tbody></table>`;
  } catch(e) { el.innerHTML = `<div class="er-table-placeholder">${t("sh.loadFailed")}</div>`; }
}

async function _shLoadCandidates() {
  const el = document.getElementById("sh-candidates-list");
  try {
    const d = await api("/api/apps/strategy_hub/candidates?limit=50");
    if (!d.candidates || !d.candidates.length) {
      el.innerHTML = `<div class="er-table-placeholder">${t("sh.noCandidates")}</div>`;
      return;
    }
    el.innerHTML = `<table class="er-table"><thead><tr>
      <th>${t("sh.colCandidateId")}</th><th>${t("sh.colSourceTask")}</th><th>${t("sh.colEffectiveSteps")}</th><th>${t("sh.colUseCount")}</th><th>${t("sh.colQualityScore")}</th><th>${t("sh.colStatus")}</th><th>${t("sh.colActions")}</th>
    </tr></thead><tbody>${d.candidates.map(c => `<tr>
      <td title="${_escHtml(c.candidate_id)}">${_escHtml(c.candidate_id.substring(0, 12))}…</td>
      <td title="${_escHtml(c.user_text)}">${_escHtml((c.user_text || '').substring(0, 30))}${(c.user_text||'').length > 30 ? '…' : ''}</td>
      <td>${c.effective_steps}</td>
      <td>${c.used_count}</td>
      <td>${c.quality_score}</td>
      <td><span class="er-badge ${c.status === 'invalid' ? 'er-badge-warn' : c.status === 'promoted' ? 'er-badge-ok' : ''}">${c.status}</span></td>
      <td>
        ${c.status !== 'promoted' && c.status !== 'invalid' ? `<button class="btn btn-sm btn-primary" onclick="_shPromoteCandidate('${_escHtml(c.candidate_id)}')">${t("sh.promote")}</button>` : ''}
        <button class="btn btn-sm btn-danger" onclick="_shDeleteCandidate('${_escHtml(c.candidate_id)}')">${t("sh.delete")}</button>
      </td>
    </tr>`).join("")}</tbody></table>`;
  } catch(e) { el.innerHTML = `<div class="er-table-placeholder">${t("sh.loadFailed")}</div>`; }
}

async function _shShowTemplateDetail(templateId) {
  const panel = document.getElementById("sh-detail-panel");
  const title = document.getElementById("sh-detail-title");
  const content = document.getElementById("sh-detail-content");
  panel.style.display = "";
  title.textContent = `${t("sh.templates")}: ${templateId.substring(0, 16)}…`;
  content.innerHTML = `<div class="er-table-placeholder">${t("sh.loading")}</div>`;

  try {
    const d = await api(`/api/apps/strategy_hub/templates/${templateId}`);
    const s = d.stats || {};
    content.innerHTML = `
      <div class="er-kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:16px;">
        <div class="er-kpi-card"><div class="er-kpi-value">${s.use_count || 0}</div><div class="er-kpi-label">${t("sh.colUseCount")}</div></div>
        <div class="er-kpi-card"><div class="er-kpi-value">${s.success_rate || 0}%</div><div class="er-kpi-label">${t("sh.colSuccessRate")}</div></div>
        <div class="er-kpi-card"><div class="er-kpi-value">${s.avg_duration_ms != null ? s.avg_duration_ms + 'ms' : '--'}</div><div class="er-kpi-label">${t("sh.avgDuration")}</div></div>
      </div>
      <div style="margin-bottom:12px;">
        <strong>${t("sh.colIntent")}:</strong> ${_escHtml(d.intent_label)} &nbsp;
        <strong>${t("sh.colVersion")}:</strong> v${d.version} &nbsp;
        <strong>${t("sh.colStatus")}:</strong> <span class="er-badge ${d.status === 'stale' ? 'er-badge-warn' : 'er-badge-ok'}">${d.status}</span>
      </div>
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer;font-weight:600;">${t("sh.planTemplate")} (${(d.plan_template || []).length} steps)</summary>
        <pre style="background:var(--bg-surface0);padding:10px;border-radius:8px;font-size:0.82rem;overflow-x:auto;max-height:300px;">${_escHtml(JSON.stringify(d.plan_template, null, 2))}</pre>
      </details>
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer;font-weight:600;">${t("sh.slotSchema")}</summary>
        <pre style="background:var(--bg-surface0);padding:10px;border-radius:8px;font-size:0.82rem;overflow-x:auto;max-height:200px;">${_escHtml(JSON.stringify(d.slot_schema, null, 2))}</pre>
      </details>
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer;font-weight:600;">${t("sh.constraints")}</summary>
        <pre style="background:var(--bg-surface0);padding:10px;border-radius:8px;font-size:0.82rem;overflow-x:auto;max-height:200px;">${_escHtml(JSON.stringify(d.constraints, null, 2))}</pre>
      </details>
      ${d.instances && d.instances.length ? `
      <h3 style="margin-top:16px;">${t("sh.relatedInstances")} (${d.instances.length})</h3>
      <table class="er-table"><thead><tr>
        <th>${t("sh.colCaseKey")}</th><th>${t("sh.colIntent")}</th><th>${t("sh.colUseCount")}</th><th>${t("sh.colSuccessRate")}</th><th>${t("sh.colLastUsed")}</th>
      </tr></thead><tbody>${d.instances.map(i => `<tr>
        <td>${_escHtml(i.case_key.substring(0, 12))}…</td>
        <td>${_escHtml(i.intent_label || '--')}</td>
        <td>${i.use_count}</td>
        <td>${i.success_rate}%</td>
        <td>${i.last_used_at ? i.last_used_at.substring(0, 10) : '--'}</td>
      </tr>`).join("")}</tbody></table>` : ''}
    `;
  } catch(e) {
    content.innerHTML = `<div class="er-table-placeholder">${t("sh.loadFailed")}: ${_escHtml(e.message)}</div>`;
  }
}

async function _shShowInstanceDetail(caseKey) {
  const panel = document.getElementById("sh-detail-panel");
  const title = document.getElementById("sh-detail-title");
  const content = document.getElementById("sh-detail-content");
  panel.style.display = "";
  title.textContent = `${t("sh.instances")}: ${caseKey.substring(0, 16)}…`;
  content.innerHTML = `<div class="er-table-placeholder">${t("sh.loading")}</div>`;

  try {
    const d = await api(`/api/apps/strategy_hub/instances/${caseKey}`);
    const s = d.stats || {};
    content.innerHTML = `
      <div class="er-kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:16px;">
        <div class="er-kpi-card"><div class="er-kpi-value">${s.use_count || 0}</div><div class="er-kpi-label">${t("sh.colUseCount")}</div></div>
        <div class="er-kpi-card"><div class="er-kpi-value">${s.success_rate || 0}%</div><div class="er-kpi-label">${t("sh.colSuccessRate")}</div></div>
        <div class="er-kpi-card"><div class="er-kpi-value">${s.avg_duration_ms != null ? s.avg_duration_ms + 'ms' : '--'}</div><div class="er-kpi-label">${t("sh.avgDuration")}</div></div>
      </div>
      <div style="margin-bottom:12px;">
        <strong>${t("sh.colIntent")}:</strong> ${_escHtml(d.intent_label || '--')} &nbsp;
        <strong>${t("sh.colTemplate")}:</strong> ${d.template_id ? _escHtml(d.template_id.substring(0, 12)) + '…' : 'N/A'} &nbsp;
        <strong>${t("sh.colStatus")}:</strong> <span class="er-badge ${d.status === 'stale' ? 'er-badge-warn' : 'er-badge-ok'}">${d.status}</span>
      </div>
      <details style="margin-bottom:12px;" ${Object.keys(d.slot_values || {}).length ? '' : 'hidden'}>
        <summary style="cursor:pointer;font-weight:600;">${t("sh.slotValues")}</summary>
        <pre style="background:var(--bg-surface0);padding:10px;border-radius:8px;font-size:0.82rem;overflow-x:auto;max-height:200px;">${_escHtml(JSON.stringify(d.slot_values, null, 2))}</pre>
      </details>
      <details style="margin-bottom:12px;">
        <summary style="cursor:pointer;font-weight:600;">${t("sh.resolvedPlan")} (${(d.resolved_plan || []).length} steps)</summary>
        <pre style="background:var(--bg-surface0);padding:10px;border-radius:8px;font-size:0.82rem;overflow-x:auto;max-height:300px;">${_escHtml(JSON.stringify(d.resolved_plan, null, 2))}</pre>
      </details>
      <div style="margin-top:12px;display:flex;gap:8px;">
        <button class="btn btn-sm" onclick="_shInvalidateInstance('${_escHtml(d.case_key)}')">${t("sh.markInvalid")}</button>
        <button class="btn btn-sm btn-danger" onclick="_shDeleteInstance('${_escHtml(d.case_key)}')">${t("sh.delete")}</button>
      </div>
    `;
  } catch(e) {
    content.innerHTML = `<div class="er-table-placeholder">${t("sh.loadFailed")}: ${_escHtml(e.message)}</div>`;
  }
}

function _shCloseDetail() {
  const panel = document.getElementById("sh-detail-panel");
  if (panel) panel.style.display = "none";
}

async function _shDeleteTemplate(templateId) {
  if (!confirm(t("sh.confirmDeleteTemplate"))) return;
  try {
    await api(`/api/apps/strategy_hub/templates/${templateId}/delete`, "POST");
    toast(t("sh.templateDeleted"), "success");
    await _shLoadTemplates();
    await _shLoadMetrics();
    _shCloseDetail();
  } catch(e) { toast(t("sh.deleteFailed") + ": " + e.message, "error"); }
}

async function _shInvalidateInstance(caseKey) {
  if (!confirm(t("sh.confirmInvalidate"))) return;
  try {
    await api(`/api/apps/strategy_hub/instances/${caseKey}/invalidate`, "POST");
    toast(t("sh.instanceInvalidated"), "success");
    await _shLoadInstances();
    await _shLoadMetrics();
  } catch(e) { toast(t("sh.operationFailed") + ": " + e.message, "error"); }
}

async function _shDeleteInstance(caseKey) {
  if (!confirm(t("sh.confirmDeleteInstance"))) return;
  try {
    await api(`/api/apps/strategy_hub/instances/${caseKey}/delete`, "POST");
    toast(t("sh.instanceDeleted"), "success");
    await _shLoadInstances();
    await _shLoadMetrics();
    _shCloseDetail();
  } catch(e) { toast(t("sh.deleteFailed") + ": " + e.message, "error"); }
}

async function _shPromoteCandidate(candidateId) {
  if (!confirm(t("sh.confirmPromote"))) return;
  try {
    const res = await api(`/api/apps/strategy_hub/candidates/${candidateId}/promote`, "POST");
    if (res.ok) {
      toast(t("sh.candidatePromoted"), "success");
      await _shLoadCandidates();
      await _shLoadInstances();
      await _shLoadMetrics();
    } else {
      toast(t("sh.promoteFailed") + ": " + (res.error || "unknown"), "error");
    }
  } catch(e) { toast(t("sh.promoteFailed") + ": " + e.message, "error"); }
}

async function _shDeleteCandidate(candidateId) {
  if (!confirm(t("sh.confirmDeleteCandidate"))) return;
  try {
    await api(`/api/apps/strategy_hub/candidates/${candidateId}/delete`, "POST");
    toast(t("sh.candidateDeleted"), "success");
    await _shLoadCandidates();
    await _shLoadMetrics();
  } catch(e) { toast(t("sh.deleteFailed") + ": " + e.message, "error"); }
}

// ── Generate Templates ────────────────────────────────────────────────

async function _shGenerateTemplates() {
  const btn = event.target.closest("button");
  if (btn) btn.disabled = true;
  
  try {
    toast(t("sh.generatingTemplates"), "info");
    const res = await api("/api/apps/strategy_hub/generate_templates", "POST", {});
    
    if (res.ok) {
      const count = res.templates_created || 0;
      if (count > 0) {
        toast(t("sh.templatesGenerated").replace("{count}", count), "success");
        // 刷新模板列表和指标
        await _shLoadTemplates();
        await _shLoadMetrics();
      } else {
        toast(res.message || t("sh.noTemplatesGenerated"), "info");
      }
    } else {
      toast(t("sh.generateFailed") + ": " + (res.error || "unknown"), "error");
    }
  } catch (e) {
    toast(t("sh.generateFailed") + ": " + e.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── End Strategy Hub ──────────────────────────────────────────────────

// ── Capability Forest Detail Page ─────────────────────────────────────

async function openCapForestDetail() {
  document.getElementById("app-detail-title").textContent = `🌲 ${t("cf.title")}`;
  switchPage("app-detail");
  const container = document.getElementById("app-detail-content");
  container.innerHTML = `<div class="app-detail-loading">${t("cf.loading")}</div>`;

  let data;
  try {
    data = await api("/api/apps/cap_forest/overview");
  } catch (e) {
    container.innerHTML = `<div class="app-detail-loading">${t("cf.loadFailed")}: ${e.message}</div>`;
    return;
  }

  const kpi = data.kpi || {};
  const active = data.active || [];
  const trial = data.trial || [];
  const candidate = data.candidate || [];
  const dormant = data.dormant || [];

  container.innerHTML = `
    <!-- KPI Cards -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">
        <span style="font-weight:600;font-size:15px">${t("cf.overview")}</span>
        <button class="btn btn-xs" onclick="cfRunPrune()" title="${t("cf.pruneDesc")}" style="margin-left:auto">${t("cf.prune")}</button>
      </div>
      <div class="er-golden-cards" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px">
        <div class="er-golden-card"><div class="er-card-label">${t("cf.kpiActive")}</div><div class="er-card-value">${kpi.active_count || 0}</div></div>
        <div class="er-golden-card"><div class="er-card-label">${t("cf.kpiTrial")}</div><div class="er-card-value">${kpi.trial_count || 0}</div></div>
        <div class="er-golden-card"><div class="er-card-label">${t("cf.kpiDormant")}</div><div class="er-card-value">${kpi.dormant_count || 0}</div></div>
        <div class="er-golden-card"><div class="er-card-label">${t("cf.kpiUse30d")}</div><div class="er-card-value">${kpi.total_use_30d || 0}</div></div>
        <div class="er-golden-card"><div class="er-card-label">${t("cf.kpiSuccess30d")}</div><div class="er-card-value">${kpi.success_rate_30d || 0}%</div></div>
        <div class="er-golden-card" style="border-left:3px solid #6366f1"><div class="er-card-label">${t("cf.mode") || "模式"}</div><div class="er-card-value" style="font-size:13px">${t("cf.advisory") || "建议"}</div></div>
      </div>
    </div>

    <!-- Evergreen (Active) -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <h3 style="margin-bottom:10px">🌿 ${t("cf.evergreen")}</h3>
      <div id="cf-active-list">${_cfRenderCapTable(active, "active")}</div>
    </div>

    <!-- Sprout (Trial) -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <h3 style="margin-bottom:10px">🌱 ${t("cf.sprout")}</h3>
      <div id="cf-trial-list">${_cfRenderCapTable(trial, "trial")}</div>
    </div>

    <!-- Seed (Recommendations) -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <h3 style="margin-bottom:10px">🫘 ${t("cf.seed")}</h3>
      <div id="cf-reco-list">${_cfRenderCandidates(candidate)}</div>
    </div>

    <!-- Dormant -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <details>
        <summary style="cursor:pointer;font-weight:600;font-size:15px">💤 ${t("cf.dormant")} (${dormant.length})</summary>
        <div id="cf-dormant-list" style="margin-top:10px">${_cfRenderCapTable(dormant, "dormant")}</div>
      </details>
    </div>

    <!-- Events -->
    <div class="app-detail-section" style="margin-bottom:18px">
      <details>
        <summary style="cursor:pointer;font-weight:600;font-size:13px;color:var(--subtext0)">${t("cf.events")}</summary>
        <div id="cf-events" style="margin-top:10px"><div class="er-table-placeholder">${t("cf.loading")}</div></div>
      </details>
    </div>
  `;

  _cfLoadEvents();
}

function _cfRenderCapTable(caps, mode) {
  if (!caps || caps.length === 0) {
    const msgKey = mode === "active" ? "cf.noActive" : mode === "trial" ? "cf.noTrial" : "cf.noDormant";
    return `<div class="er-table-placeholder" style="padding:16px;color:var(--subtext0);font-size:13px">${t(msgKey)}</div>`;
  }
  const rows = caps.map(c => {
    const useCount = c.use_count_30d || 0;
    const successCount = c.success_count_30d || 0;
    const successRate = useCount > 0 ? Math.round(successCount / useCount * 100) : 0;
    const lastUsed = c.last_used_at ? c.last_used_at.slice(0, 10) : "--";
    const score = (c.score || 0).toFixed(1);
    const typeBadge = `<span class="cf-type-badge cf-type-${c.cap_type || 'core'}">${c.cap_type || 'core'}</span>`;

    let actions = "";
    if (mode === "active") {
      actions = `<button class="btn btn-xs btn-danger" onclick="cfDisableCap('${c.cap_id}')">${t("cf.disable")}</button>`;
    } else if (mode === "trial") {
      actions = `<button class="btn btn-xs btn-primary" onclick="cfPromoteCap('${c.cap_id}')">${t("cf.promote")}</button>
                 <button class="btn btn-xs btn-danger" onclick="cfDisableCap('${c.cap_id}')">${t("cf.disable")}</button>`;
    } else if (mode === "dormant") {
      actions = `<button class="btn btn-xs btn-primary" onclick="cfEnableCap('${c.cap_id}','active')">${t("cf.wake")}</button>
                 <button class="btn btn-xs" onclick="cfEnableCap('${c.cap_id}','trial')">${t("cf.enableTrial")}</button>`;
    }

    return `<tr>
      <td style="font-weight:500">${c.name || c.cap_id} ${typeBadge}</td>
      <td>${useCount}</td>
      <td>${successRate}%</td>
      <td>${lastUsed}</td>
      <td>${score}</td>
      <td>${actions}</td>
    </tr>`;
  }).join("");

  return `<table class="er-table" style="width:100%;font-size:13px">
    <thead><tr>
      <th>${t("cf.colName")}</th>
      <th>${t("cf.colUseCount")}</th>
      <th>${t("cf.colSuccessRate")}</th>
      <th>${t("cf.colLastUsed")}</th>
      <th>${t("cf.colScore")}</th>
      <th>${t("cf.colActions")}</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function _cfRenderCandidates(caps) {
  if (!caps || caps.length === 0) {
    return `<div class="er-table-placeholder" style="padding:16px;color:var(--subtext0);font-size:13px">${t("cf.noReco")}</div>`;
  }
  return caps.map(c => {
    let tags = "";
    try { tags = JSON.parse(c.tags_json || "[]").join(", "); } catch(_) {}
    let intents = "";
    try { intents = JSON.parse(c.intents_json || "[]").join(", "); } catch(_) {}
    const desc = c.description || "";
    return `<div class="er-golden-card" style="padding:14px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-weight:600">${c.name || c.cap_id}</span>
        <span class="cf-type-badge cf-type-${c.cap_type || 'core'}">${c.cap_type || 'mcp'}</span>
      </div>
      <div style="font-size:12px;color:var(--subtext0);margin-bottom:8px">${desc}</div>
      ${tags ? `<div style="font-size:11px;color:var(--subtext1);margin-bottom:6px">Tags: ${tags}</div>` : ""}
      ${intents ? `<div style="font-size:11px;color:var(--subtext1);margin-bottom:8px">Intents: ${intents}</div>` : ""}
      <div style="display:flex;gap:6px">
        <button class="btn btn-xs btn-primary" onclick="cfEnableCap('${c.cap_id}','trial')">${t("cf.enableTrial")}</button>
        <button class="btn btn-xs" onclick="cfEnableCap('${c.cap_id}','active')">${t("cf.enable")}</button>
      </div>
    </div>`;
  }).join("");
}

async function _cfLoadEvents() {
  const el = document.getElementById("cf-events");
  if (!el) return;
  try {
    const data = await api("/api/apps/cap_forest/events?limit=50");
    const events = data.events || [];
    if (events.length === 0) {
      el.innerHTML = `<div class="er-table-placeholder" style="padding:12px;color:var(--subtext0);font-size:12px">${t("cf.noEvents")}</div>`;
      return;
    }
    el.innerHTML = `<table class="er-table" style="width:100%;font-size:12px">
      <thead><tr><th>Time</th><th>Event</th><th>Capability</th><th>Details</th></tr></thead>
      <tbody>${events.map(e => {
        let meta = "";
        try { const m = JSON.parse(e.meta_json || "{}"); meta = Object.entries(m).map(([k,v])=>`${k}=${v}`).join(", "); } catch(_) {}
        return `<tr><td>${(e.ts||"").slice(0,19)}</td><td>${e.event_type}</td><td>${e.cap_id}</td><td style="color:var(--subtext0)">${meta}</td></tr>`;
      }).join("")}</tbody>
    </table>`;
  } catch(e) {
    el.innerHTML = `<div class="er-table-placeholder" style="color:var(--red)">${e.message}</div>`;
  }
}

async function cfEnableCap(capId, mode) {
  try {
    await api("/api/apps/cap_forest/cap/enable", { method: "POST", body: JSON.stringify({ cap_id: capId, mode }) });
    await openCapForestDetail();
  } catch(e) { toast(e.message, "error"); }
}

async function cfDisableCap(capId) {
  if (!confirm(t("cf.confirmDisable"))) return;
  try {
    await api("/api/apps/cap_forest/cap/disable", { method: "POST", body: JSON.stringify({ cap_id: capId }) });
    await openCapForestDetail();
  } catch(e) { toast(e.message, "error"); }
}

async function cfPromoteCap(capId) {
  if (!confirm(t("cf.confirmPromote"))) return;
  try {
    await api("/api/apps/cap_forest/cap/promote", { method: "POST", body: JSON.stringify({ cap_id: capId }) });
    await openCapForestDetail();
  } catch(e) { toast(e.message, "error"); }
}

async function cfRunPrune() {
  try {
    const res = await api("/api/apps/cap_forest/prune/run", { method: "POST" });
    toast(t("cf.pruned").replace("{count}", res.count || 0), "success");
    await openCapForestDetail();
  } catch(e) { toast(e.message, "error"); }
}

// ── End Capability Forest ─────────────────────────────────────────────

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
      headers: authHeaders({ "Content-Type": "application/json" }),
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
      headers: authHeaders({ "Content-Type": "application/json" }),
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
  const alertInd = document.getElementById("token-alert-ind");
  if (!tokEl || !searchEl) return;
  try {
    const [tok, search, costDec] = await Promise.all([
      api("/api/token/usage").catch(() => null),
      api("/api/search/usage").catch(() => null),
      api("/api/cost/decision").catch(() => null),
    ]);
    if (tok) {
      const inp = tok.input_tokens || 0;
      const out = tok.output_tokens || 0;
      const cost = tok.cost || 0;
      const alertLevel = tok.alert_level || "green";
      
      // Update alert indicator
      if (alertInd) {
        alertInd.className = `token-alert-indicator ${alertLevel}`;
      }
      
      // Build display text
      let displayText = `${t("stats.todayPrefix")} ↓${_fmtNum(inp)} ↑${_fmtNum(out)}`;
      if (cost > 0) {
        displayText += ` ¥${cost.toFixed(2)}`;
      }
      if (costDec && costDec.model_tier && costDec.model_tier !== "max") {
        displayText += ` [${costDec.model_tier}]`;
      }
      if (costDec && !costDec.allow_llm) {
        displayText += " ⛔";
      }
      
      // Update text (keep indicator at front)
      const indicator = tokEl.querySelector('.token-alert-indicator');
      tokEl.textContent = displayText;
      if (indicator) tokEl.prepend(indicator);
      
      // Build tooltip
      let tooltip = t("stats.tokenTip");
      if (cost > 0) {
        tooltip += `\n${t("stats.costTip")}: ¥${cost.toFixed(2)}`;
      }
      if (tok.daily_limit > 0) {
        const dailyUsage = (inp + out) / 1000000;  // convert to M tokens
        tooltip += `\n日使用: ${dailyUsage.toFixed(2)}M/${tok.daily_limit}M token (${tok.daily_usage_pct.toFixed(1)}%)`;
      }
      if (tok.monthly_limit > 0 && tok.monthly_cost !== undefined) {
        tooltip += `\n月预警: ${tok.monthly_usage_pct.toFixed(1)}%`;
      }
      if (costDec && costDec.reason) {
        tooltip += `\n成本控制: ${costDec.reason}`;
      }
      tokEl.title = tooltip;
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
  const dot = document.getElementById("task-running-dot");
  const btn = document.getElementById("task-nav-btn");

  const alertCount = tasks.filter(t => t.status === "failed" || t.status === "pending_catchup").length;
  const hasRunning = tasks.some(t => t.status === "running");

  if (badge) {
    if (alertCount > 0) {
      badge.textContent = String(alertCount);
      badge.classList.add("visible");
    } else {
      badge.textContent = "";
      badge.classList.remove("visible");
    }
  }

  if (dot) {
    dot.classList.toggle("visible", hasRunning);
  }

  if (btn) {
    btn.classList.toggle("has-active", hasRunning || alertCount > 0);
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
    const isRunning = task.status === "running";
    const runBtn = isRunning
      ? `<span class="task-running-indicator">⏳</span>`
      : `<button class="task-run-btn" onclick="triggerTask('${_escAttr(task.task_id)}')" title="${t("tasks.runNow")}">▶</button>`;
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
    const resp = await fetch("/api/audit/export", { headers: authHeaders() });
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
  loadSecretsInfo();
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

async function loadSecretsInfo() {
  try {
    const data = await api("/api/profile/secrets/info");
    const badge = document.getElementById("secrets-backend-badge");
    const count = document.getElementById("secrets-count");
    if (badge) {
      const name = data.backend === "keyring" ? t("privacy.backendKeyring") : t("privacy.backendFile");
      badge.textContent = `${t("privacy.backend")}: ${name}`;
    }
    if (count) {
      const n = (data.stored_keys || []).length;
      count.textContent = `${t("privacy.storedKeys")}: ${n}`;
    }
  } catch (_) {}
}

async function clearAllSecrets() {
  if (!confirm(t("privacy.clearSecretsConfirm"))) return;
  try {
    await api("/api/profile/secrets/clear", "POST");
    toast(t("privacy.secretsCleared"), "success");
    loadSecretsInfo();
  } catch (e) {
    toast(`Error: ${e}`, "error");
  }
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

