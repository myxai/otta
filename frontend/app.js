/* ===================================================================
   nanobot Desktop — Frontend Logic
   =================================================================== */

// ── i18n ──────────────────────────────────────────────────────────────

const I18N = {
  zh: {
    "nav.newChat":"新对话","nav.settings":"设置","nav.status":"状态","nav.gateway":"网关",
    "setup.welcome":"欢迎使用 nanobot Desktop",
    "setup.install.title":"安装 nanobot","setup.install.desc":"在终端运行以下命令：",
    "setup.onboard.title":"初始化配置","setup.onboard.desc":"点击下方按钮自动初始化。","setup.onboard.btn":"初始化 nanobot",
    "setup.apikey.title":"配置 API Key","setup.apikey.desc":"前往「设置」页面填写您的 API Key。","setup.apikey.btn":"前往设置",
    "chat.ready":"nanobot 已就绪","chat.readyDesc":"输入消息开始对话，我可以帮你搜索信息、编写代码、管理文件等。",
    "chat.placeholder":"输入消息… (Enter 发送, Shift+Enter 换行)",
    "chat.you":"你","chat.noHistory":"暂无历史对话","chat.newChat":"新对话",
    "chat.rename":"重命名","chat.renameTitle":"修改对话标题","chat.renamePlaceholder":"输入新标题",
    "chat.regenerate":"重新回答",
    "chat.rated":"已评价","chat.thankFeedback":"感谢反馈！","chat.willImprove":"已记录，会改进",
    "chat.askDislike":"可以说说哪里不满意吗？（可留空）",
    "chat.error":"错误: ","chat.requestFail":"请求失败: ",
    "settings.title":"设置","settings.save":"保存配置",
    "settings.model":"模型设置","settings.modelName":"模型名称",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"最大工具迭代次数","settings.memoryWindow":"记忆窗口大小",
    "settings.apiKeys":"API 密钥",
    "settings.searchTools":"搜索与工具","settings.braveKey":"Brave Search API Key",
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
    "nav.apps":"应用",
    "apps.title":"应用中心","apps.search":"搜索应用…","apps.back":"返回",
    "apps.installed":"已安装","apps.notInstalled":"未安装","apps.comingSoon":"即将推出",
    "apps.install":"安装","apps.uninstall":"卸载","apps.configure":"配置",
    "apps.enabled":"已启用","apps.disabled":"已停用",
    "apps.enable":"启用","apps.disable":"停用",
    "apps.installOk":"应用安装成功","apps.uninstallOk":"应用已卸载",
    "apps.installFail":"安装失败","apps.uninstallFail":"卸载失败",
    "apps.version":"版本","apps.author":"作者",
    "digest.title":"推荐日报","digest.subtitle":"基于浏览器历史，AI 自动分析兴趣并全网搜索推荐",
    "digest.status":"状态","digest.config":"配置",
    "digest.browser":"浏览器","digest.browserAuto":"自动检测","digest.browserChrome":"Chrome","digest.browserEdge":"Edge",
    "digest.historyHours":"历史范围（小时）","digest.scheduleTime":"每日生成时间",
    "digest.pushNotification":"弹窗提醒","digest.pushEmail":"邮箱推送",
    "digest.runNow":"立即生成","digest.running":"正在生成…","digest.saveConfig":"保存设置",
    "digest.configSaved":"设置已保存","digest.configFail":"保存失败",
    "digest.reports":"历史报告","digest.noReports":"暂无报告",
    "digest.preview":"兴趣预览","digest.previewDesc":"快速分析当前浏览器历史中的兴趣分布（优先使用 AI 分析）",
    "digest.previewBtn":"预览兴趣","digest.previewLoading":"正在分析…",
    "digest.previewMethod":"分析方式","digest.previewRuleBased":"规则",
    "digest.work":"工作","digest.study":"学习","digest.life":"生活",
    "digest.rawCount":"原始记录","digest.filteredCount":"有效记录","digest.keywordCount":"兴趣数","digest.searchResults":"搜索推荐",
    "digest.viewReport":"查看","digest.lastRun":"上次运行",
    "digest.generating":"日报生成中，请稍候…","digest.generateOk":"日报生成完成！",
    "digest.generateFail":"日报生成失败","digest.noHistory":"未找到浏览记录",
    "digest.latestReport":"最新报告",
  },
  en: {
    "nav.newChat":"New Chat","nav.settings":"Settings","nav.status":"Status","nav.gateway":"Gateway",
    "setup.welcome":"Welcome to nanobot Desktop",
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
    "settings.title":"Settings","settings.save":"Save",
    "settings.model":"Model Settings","settings.modelName":"Model Name",
    "settings.maxTokens":"Max Tokens","settings.maxIter":"Max Tool Iterations","settings.memoryWindow":"Memory Window Size",
    "settings.apiKeys":"API Keys",
    "settings.searchTools":"Search & Tools","settings.braveKey":"Brave Search API Key",
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
    "nav.apps":"Apps",
    "apps.title":"App Center","apps.search":"Search apps…","apps.back":"Back",
    "apps.installed":"Installed","apps.notInstalled":"Not installed","apps.comingSoon":"Coming Soon",
    "apps.install":"Install","apps.uninstall":"Uninstall","apps.configure":"Configure",
    "apps.enabled":"Enabled","apps.disabled":"Disabled",
    "apps.enable":"Enable","apps.disable":"Disable",
    "apps.installOk":"App installed successfully","apps.uninstallOk":"App uninstalled",
    "apps.installFail":"Install failed","apps.uninstallFail":"Uninstall failed",
    "apps.version":"Version","apps.author":"Author",
    "digest.title":"Daily Digest","digest.subtitle":"AI-powered interest analysis and web search based on browser history",
    "digest.status":"Status","digest.config":"Settings",
    "digest.browser":"Browser","digest.browserAuto":"Auto detect","digest.browserChrome":"Chrome","digest.browserEdge":"Edge",
    "digest.historyHours":"History range (hours)","digest.scheduleTime":"Daily generation time",
    "digest.pushNotification":"Push notification","digest.pushEmail":"Email push",
    "digest.runNow":"Generate Now","digest.running":"Generating…","digest.saveConfig":"Save Settings",
    "digest.configSaved":"Settings saved","digest.configFail":"Save failed",
    "digest.reports":"Report History","digest.noReports":"No reports yet",
    "digest.preview":"Interest Preview","digest.previewDesc":"Quick analysis of current browser history interests (AI-powered when available)",
    "digest.previewBtn":"Preview Interests","digest.previewLoading":"Analyzing…",
    "digest.previewMethod":"Method","digest.previewRuleBased":"Rule-based",
    "digest.work":"Work","digest.study":"Study","digest.life":"Life",
    "digest.rawCount":"Raw records","digest.filteredCount":"Valid records","digest.keywordCount":"Interests","digest.searchResults":"Recommendations",
    "digest.viewReport":"View","digest.lastRun":"Last run",
    "digest.generating":"Generating digest, please wait…","digest.generateOk":"Digest generated!",
    "digest.generateFail":"Generation failed","digest.noHistory":"No browser history found",
    "digest.latestReport":"Latest Report",
  },
};

let _lang = "zh";

function detectLang() {
  const stored = localStorage.getItem("nanobot_lang");
  if (stored && stored !== "auto") return stored;
  const nav = (navigator.language || "").toLowerCase();
  return nav.startsWith("zh") ? "zh" : "en";
}

function t(key) { return (I18N[_lang] && I18N[_lang][key]) || (I18N.zh[key]) || key; }

function setLanguage(val) {
  localStorage.setItem("nanobot_lang", val);
  _lang = (val === "auto") ? detectLang() : val;
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = val;
  const radio = document.querySelector(`input[name="lang-radio"][value="${val}"]`);
  if (radio) radio.checked = true;
  applyLanguage();
}

function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return;
    el.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  renderChatFromHistory();
  renderSessionList();
  const chatInput = document.getElementById("chat-input");
  if (chatInput) chatInput.placeholder = t("chat.placeholder");
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
  setupInput();
  setTimeout(hideSplash, 6000);
  await checkSystem();
});

function hideSplash() {
  const splash = document.getElementById("splash");
  const app = document.getElementById("app-root");
  if (splash) splash.classList.add("hidden");
  if (app) app.style.opacity = "1";
}

async function checkSystem() {
  try {
    const [res] = await Promise.all([
      api("/api/check"),
      window.__libsReady || Promise.resolve(),
    ]);
    if (!res.nanobot_installed) {
      hideSplash();
      applyLanguage();
      showSetup("install");
      return;
    }
    if (!res.config_exists) {
      hideSplash();
      applyLanguage();
      showSetup("onboard");
      return;
    }
    await Promise.all([loadSessionList(), loadConfig()]);
    await loadLastSessionOrNew();
    switchPage("chat");
    applyLanguage();
    hideSplash();
    startNotificationPoll();
  } catch (e) {
    hideSplash();
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
  if (page === "settings") loadConfig();
  if (page === "status") loadStatus();
  if (page === "gateway") loadGatewayStatus();
  if (page === "apps") loadApps();
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
      return `<div class="session-item${active}" data-sid="${sid}" onclick="switchSession('${sid}')">
        <span class="session-icon">💬</span>
        <span class="session-title" title="${title}" ondblclick="event.stopPropagation();startRenameSession('${sid}')">${title}</span>
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
  chatMessages = [];
  try { const res = await api(`/api/history/${encodeURIComponent(sid)}`); chatMessages = res.messages || []; } catch (_) {}
  renderChatFromHistory();
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
        <div class="welcome-icon">🐈</div>
        <h2>${t("chat.ready")}</h2>
        <p>${t("chat.readyDesc")}</p>
      </div>`;
    return;
  }
  container.innerHTML = "";
  for (let i = 0; i < chatMessages.length; i++) {
    const msg = chatMessages[i];
    appendMessageDOM(msg.role, msg.content, !!msg.markdown, i, msg.feedback || null);
  }
}

async function sendMessage() {
  if (chatBusy) return;
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "auto";
  document.getElementById("send-btn").disabled = true;
  chatBusy = true;

  clearWelcome();
  appendMessageDOM("user", text);
  chatMessages.push({ role: "user", content: text, markdown: false });
  const thinkingId = appendThinking();

  let finalContent = null;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let progressEl = null;

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
            if (!progressEl) { removeElement(thinkingId); progressEl = appendMessageDOM("bot progress", "↳ " + data.content); }
            else updateMessageContent(progressEl, "↳ " + data.content);
          } else if (data.type === "done") {
            finalContent = data.content;
          } else if (data.type === "error") {
            removeElement(thinkingId);
            if (progressEl) removeElement(progressEl);
            appendMessageDOM("bot", t("chat.error") + data.content);
            finalContent = t("chat.error") + data.content;
          }
        } catch (_) {}
      }
    }

    removeElement(thinkingId);
    if (progressEl) removeElement(progressEl);
    if (finalContent !== null) {
      chatMessages.push({ role: "bot", content: finalContent, markdown: true, feedback: null });
      appendMessageDOM("bot", finalContent, true, chatMessages.length - 1, null);
    }
  } catch (e) {
    removeElement(thinkingId);
    finalContent = t("chat.requestFail") + e.message;
    chatMessages.push({ role: "bot", content: finalContent, markdown: false, feedback: null });
    appendMessageDOM("bot", finalContent, false, chatMessages.length - 1, null);
  }
  await persistCurrentSession();
  chatBusy = false;
  document.getElementById("send-btn").disabled = false;
  input.focus();
}

async function persistCurrentSession() {
  if (!chatMessages.length) return;
  const firstUser = chatMessages.find((m) => m.role === "user");
  const title = firstUser ? firstUser.content.slice(0, 50) : t("chat.newChat");
  try { await api(`/api/history/${encodeURIComponent(sessionId)}`, "POST", { title, messages: chatMessages }); } catch (_) {}
  await loadSessionList();
}

async function newChat(skipPageSwitch = false) {
  try { const res = await api("/api/chat/new", "POST"); if (res.session_id) sessionId = res.session_id; }
  catch (_) { sessionId = "desktop:" + Date.now(); }
  chatMessages = [];
  renderChatFromHistory();
  renderSessionList();
  if (!skipPageSwitch) switchPage("chat");
}

function clearWelcome() { const w = document.querySelector(".welcome-message"); if (w) w.remove(); }

function appendMessageDOM(type, content, renderMd = false, msgIndex = -1, existingFeedback = null) {
  const container = document.getElementById("chat-messages");
  const id = "msg-" + Date.now() + Math.random().toString(36).slice(2, 6);
  const isUser = type.includes("user");
  const isProgress = type.includes("progress");
  const isBotFinal = !isUser && !isProgress;
  const className = isUser ? "message user" : isProgress ? "message bot progress" : "message bot";

  const div = document.createElement("div");
  div.className = className;
  div.id = id;

  const avatar = isUser ? "👤" : "🐈";
  const sender = isUser ? t("chat.you") : "nanobot";
  const rendered = renderMd ? renderMarkdown(content) : escapeHtml(content);

  let feedbackHtml = "";
  if (isBotFinal && msgIndex >= 0) {
    const likeClass = existingFeedback === "like" ? " selected-like" : existingFeedback === "dislike" ? " dimmed" : "";
    const dislikeClass = existingFeedback === "dislike" ? " selected-dislike" : existingFeedback === "like" ? " dimmed" : "";
    const commentText = existingFeedback ? `<span class="feedback-comment">${t("chat.rated")}</span>` : "";
    feedbackHtml = `<div class="message-feedback" data-msgindex="${msgIndex}">
      <button class="feedback-btn${likeClass}" data-rating="like" onclick="handleFeedback(this)">👍</button>
      <button class="feedback-btn${dislikeClass}" data-rating="dislike" onclick="handleFeedback(this)">👎</button>
      <button class="feedback-btn regenerate-btn" onclick="regenerateMessage(${msgIndex})" title="${t("chat.regenerate")}">🔄</button>
      ${commentText}
    </div>`;
  }

  div.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-sender">${sender}</div>
      <div class="message-content">${rendered}</div>
      ${feedbackHtml}
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  if (renderMd) highlightCode(div);
  return id;
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
  const thinkingId = appendThinking();

  let finalContent = null;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText, session_id: sessionId }),
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let progressEl = null;

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
            if (!progressEl) { removeElement(thinkingId); progressEl = appendMessageDOM("bot progress", "↳ " + data.content); }
            else updateMessageContent(progressEl, "↳ " + data.content);
          } else if (data.type === "done") {
            finalContent = data.content;
          } else if (data.type === "error") {
            removeElement(thinkingId);
            if (progressEl) removeElement(progressEl);
            appendMessageDOM("bot", t("chat.error") + data.content);
            finalContent = t("chat.error") + data.content;
          }
        } catch (_) {}
      }
    }

    removeElement(thinkingId);
    if (progressEl) removeElement(progressEl);
    if (finalContent !== null) {
      chatMessages.push({ role: "bot", content: finalContent, markdown: true, feedback: null });
      appendMessageDOM("bot", finalContent, true, chatMessages.length - 1, null);
    }
  } catch (e) {
    removeElement(thinkingId);
    finalContent = t("chat.requestFail") + e.message;
    chatMessages.push({ role: "bot", content: finalContent, markdown: false, feedback: null });
    appendMessageDOM("bot", finalContent, false, chatMessages.length - 1, null);
  }
  await persistCurrentSession();
  chatBusy = false;
  document.getElementById("send-btn").disabled = false;
}

function appendThinking() {
  const container = document.getElementById("chat-messages");
  const id = "thinking-" + Date.now();
  const div = document.createElement("div");
  div.className = "message bot"; div.id = id;
  div.innerHTML = `<div class="message-avatar">🐈</div><div class="message-body"><div class="message-sender">nanobot</div><div class="message-content"><div class="thinking-dots"><span></span><span></span><span></span></div></div></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
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
  document.getElementById("cfg-brave-key").value = get(cfg, ["tools", "web", "search", "apiKey"]) || "";
  document.getElementById("cfg-exec-timeout").value = get(cfg, ["tools", "exec", "timeout"]) || "";
  document.getElementById("cfg-restrict-workspace").checked = !!get(cfg, ["tools", "restrictToWorkspace"]);

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
  set(cfg, ["agents", "defaults", "model"], document.getElementById("cfg-model").value);
  set(cfg, ["agents", "defaults", "temperature"], parseFloat(document.getElementById("cfg-temperature").value) || 0.7);
  const maxTokens = parseInt(document.getElementById("cfg-max-tokens").value);
  if (maxTokens) set(cfg, ["agents", "defaults", "maxTokens"], maxTokens);
  const maxIter = parseInt(document.getElementById("cfg-max-iterations").value);
  if (maxIter) set(cfg, ["agents", "defaults", "maxToolIterations"], maxIter);
  const memWin = parseInt(document.getElementById("cfg-memory-window").value);
  if (memWin) set(cfg, ["agents", "defaults", "memoryWindow"], memWin);
  PROVIDER_FIELDS.forEach(({ id, path }) => { const val = document.getElementById(id).value; if (val) set(cfg, path, val); });
  const braveKey = document.getElementById("cfg-brave-key").value;
  if (braveKey) set(cfg, ["tools", "web", "search", "apiKey"], braveKey);
  const execTimeout = parseInt(document.getElementById("cfg-exec-timeout").value);
  if (execTimeout) set(cfg, ["tools", "exec", "timeout"], execTimeout);
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
  const opts = { method, headers: {} };
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

async function loadApps() {
  try {
    _appsCache = await api("/api/apps");
  } catch (_) {
    _appsCache = [];
  }
  renderApps(_appsCache);
}

function filterApps(query) {
  if (!query) { renderApps(_appsCache); return; }
  const q = query.toLowerCase();
  const filtered = _appsCache.filter(a =>
    (a.name || "").toLowerCase().includes(q) ||
    (a.name_en || "").toLowerCase().includes(q) ||
    (a.description || "").toLowerCase().includes(q) ||
    (a.description_en || "").toLowerCase().includes(q)
  );
  renderApps(filtered);
}

function _appName(a) { return _lang === "en" ? (a.name_en || a.name) : a.name; }
function _appDesc(a) { return _lang === "en" ? (a.description_en || a.description) : a.description; }

function renderApps(apps) {
  const grid = document.getElementById("apps-grid");
  if (!apps.length) {
    grid.innerHTML = `<div class="apps-empty">${t("apps.search")}</div>`;
    return;
  }

  grid.innerHTML = apps.map(a => {
    const name = escapeHtml(_appName(a));
    const desc = escapeHtml(_appDesc(a));
    const ver = escapeHtml(a.version || "1.0.0");
    const icon = a.icon || "📦";
    const isInstalled = a.installed;
    const isEnabled = a.enabled;
    const comingSoon = a.coming_soon;

    let statusBadge = "";
    let actions = "";

    if (comingSoon) {
      statusBadge = `<span class="app-badge app-badge-soon">${t("apps.comingSoon")}</span>`;
    } else if (isInstalled) {
      statusBadge = isEnabled
        ? `<span class="app-badge app-badge-on">${t("apps.enabled")}</span>`
        : `<span class="app-badge app-badge-off">${t("apps.disabled")}</span>`;
      actions = `
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();openAppDetail('${a.id}')">${t("apps.configure")}</button>
        <button class="btn btn-sm" onclick="event.stopPropagation();uninstallApp('${a.id}')">${t("apps.uninstall")}</button>`;
    } else {
      statusBadge = `<span class="app-badge app-badge-new">${t("apps.notInstalled")}</span>`;
      actions = `<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();installApp('${a.id}')">${t("apps.install")}</button>`;
    }

    return `<div class="app-card${isInstalled ? ' installed' : ''}${comingSoon ? ' coming-soon' : ''}" onclick="${isInstalled && !comingSoon ? `openAppDetail('${a.id}')` : ''}">
      <div class="app-card-header">
        <div class="app-card-icon">${icon}</div>
        ${statusBadge}
      </div>
      <div class="app-card-body">
        <h3 class="app-card-name">${name}</h3>
        <p class="app-card-desc">${desc}</p>
        <div class="app-card-meta">
          <span>${t("apps.version")} ${ver}</span>
        </div>
      </div>
      <div class="app-card-actions">${actions}</div>
    </div>`;
  }).join("");
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
  if (!confirm(_lang === "zh" ? "确定要卸载此应用吗？" : "Uninstall this app?")) return;
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
  if (appId === "daily_digest") {
    await openDigestDetail();
    return;
  }
  toast("This app has no configuration page yet.", "info");
}

async function openDigestDetail() {
  document.getElementById("app-detail-title").textContent = `📰 ${t("digest.title")}`;
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

  title.textContent = `📅 ${reportData.date || ""} ${t("digest.latestReport")}`;
  const raw = reportData.content || "";
  // New reports are HTML (start with "<"); legacy reports may be Markdown
  content.innerHTML = raw.trimStart().startsWith("<") ? raw : renderMarkdown(raw);
  section.style.display = "block";
  section.scrollIntoView({ behavior: "smooth" });
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
    let html = `<div class="digest-preview-stats">
      <div class="digest-stat"><span class="digest-stat-num">${data.raw_count}</span><span class="digest-stat-label">${t("digest.rawCount")}</span></div>
      <div class="digest-stat"><span class="digest-stat-num">${data.filtered_count}</span><span class="digest-stat-label">${t("digest.filteredCount")}</span></div>
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
