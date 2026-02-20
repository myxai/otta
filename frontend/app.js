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
  } catch (e) {
    hideSplash();
    applyLanguage();
    showSetup("install");
  }
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
    n.classList.toggle("active", n.dataset.page === page);
  });
  if (page === "settings") loadConfig();
  if (page === "status") loadStatus();
  if (page === "gateway") loadGatewayStatus();
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
  if (isBotFinal) {
    const likeClass = existingFeedback === "like" ? " selected-like" : existingFeedback === "dislike" ? " dimmed" : "";
    const dislikeClass = existingFeedback === "dislike" ? " selected-dislike" : existingFeedback === "like" ? " dimmed" : "";
    const commentText = existingFeedback ? `<span class="feedback-comment">${t("chat.rated")}</span>` : "";
    feedbackHtml = `<div class="message-feedback" data-msgindex="${msgIndex}">
      <button class="feedback-btn${likeClass}" data-rating="like" onclick="handleFeedback(this)">👍</button>
      <button class="feedback-btn${dislikeClass}" data-rating="dislike" onclick="handleFeedback(this)">👎</button>
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

function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  div.textContent = message;
  container.appendChild(div);
  setTimeout(() => div.remove(), 4000);
}
