"""Email Summary App — connect via IMAP, read recent emails, generate LLM summary.

Uses Python built-in `imaplib` + `email` — no extra dependencies required.
"""

import email
import email.header
import email.utils
import imaplib
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_APP_DIR = Path.home() / ".nanobot" / "apps" / "email_summary"
_REPORTS_DIR = _APP_DIR / "reports"

# ── IMAP presets for popular providers ──────────────────────────────

IMAP_PRESETS = {
    "qq":      {"host": "imap.qq.com",       "port": 993, "ssl": True},
    "163":     {"host": "imap.163.com",       "port": 993, "ssl": True},
    "gmail":   {"host": "imap.gmail.com",     "port": 993, "ssl": True},
    "outlook": {"host": "outlook.office365.com", "port": 993, "ssl": True},
    "126":     {"host": "imap.126.com",       "port": 993, "ssl": True},
    "yeah":    {"host": "imap.yeah.net",      "port": 993, "ssl": True},
    "aliyun":  {"host": "imap.aliyun.com",    "port": 993, "ssl": True},
}


# ── Persistence ─────────────────────────────────────────────────────

def _ensure_dirs():
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    _REPORTS_DIR.mkdir(exist_ok=True)


def list_reports() -> list[dict]:
    _ensure_dirs()
    reports = []
    for fp in sorted(_REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            meta = json.loads(fp.read_text(encoding="utf-8"))
            reports.append({
                "date": fp.stem,
                "email_count": meta.get("email_count", 0),
                "generated_at": meta.get("generated_at", ""),
            })
        except Exception:
            pass
    return reports


def get_report(date_str: str) -> dict | None:
    fp = _REPORTS_DIR / f"{date_str}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def delete_report(date_str: str) -> bool:
    from apps.safe_fs import safe_remove
    fp = _REPORTS_DIR / f"{date_str}.json"
    if fp.exists():
        safe_remove(fp)
        return True
    return False


def _save_report(date_str: str, data: dict):
    _ensure_dirs()
    (_REPORTS_DIR / f"{date_str}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )


# ── IMAP helpers ────────────────────────────────────────────────────

def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    result = []
    for data, charset in parts:
        if isinstance(data, bytes):
            result.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(data)
    return " ".join(result)


def _extract_body(msg: email.message.Message, max_len: int = 500) -> str:
    """Extract plain-text body preview."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
            elif ct == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    body = re.sub(r"<[^>]+>", " ", html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                body = re.sub(r"<[^>]+>", " ", body)

    body = re.sub(r"\s+", " ", body).strip()
    return body[:max_len]


def connect_imap(host: str, port: int, user: str, password: str, use_ssl: bool = True):
    """Connect and login. Returns the IMAP connection."""
    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)
    conn.login(user, password)
    return conn


def test_connection(config: dict) -> dict:
    """Test IMAP connection. Returns {success, message}."""
    try:
        conn = connect_imap(
            config["imap_host"], config.get("imap_port", 993),
            config["imap_user"], config["imap_password"],
            config.get("imap_ssl", True),
        )
        conn.select(config.get("imap_folder", "INBOX"), readonly=True)
        conn.logout()
        return {"success": True, "message": "连接成功"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


_IMAP_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _imap_date(dt: datetime) -> str:
    """Format datetime as IMAP date string (locale-independent)."""
    return f"{dt.day:02d}-{_IMAP_MONTHS[dt.month - 1]}-{dt.year}"


def _parse_email_date(date_str: str) -> datetime | None:
    """Parse an email Date header into a timezone-aware datetime."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def fetch_recent_emails(
    conn,
    folder: str = "INBOX",
    hours: int = 24,
    max_count: int = 50,
) -> list[dict]:
    """Fetch emails from the given time range.

    Uses IMAP SINCE as a rough server-side pre-filter (day granularity),
    then applies precise client-side filtering on the actual send time.
    """
    conn.select(folder, readonly=True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    # IMAP SINCE is date-only; go back one extra day to be safe
    since_date = _imap_date(cutoff - timedelta(days=1))
    _, msg_nums = conn.search(None, f'(SINCE "{since_date}")')
    ids = msg_nums[0].split()
    if not ids:
        return []

    # Fetch from newest first, stop early once we have enough
    ids = list(reversed(ids))
    emails = []
    for mid in ids:
        if len(emails) >= max_count:
            break
        try:
            _, data = conn.fetch(mid, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            date_str = msg["Date"] or ""
            sent_dt = _parse_email_date(date_str)
            if sent_dt and sent_dt < cutoff:
                continue
            subject = _decode_header(msg["Subject"])
            from_ = _decode_header(msg["From"])
            body = _extract_body(msg)
            emails.append({
                "subject": subject,
                "from": from_,
                "date": date_str,
                "body_preview": body,
            })
        except Exception:
            continue

    emails.reverse()
    return emails


# ── Summary generation ──────────────────────────────────────────────

def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_EMAIL_JSON_SCHEMA = """\
{
  "categories": [
    {
      "name": "分类名称（如：需要回复、项目进展、知识分享、通知/订阅等）",
      "icon": "适合的emoji",
      "summary": "这个分类下邮件的整体情况总结（1-2句）",
      "highlights": ["要点1", "要点2"]
    }
  ],
  "attention": ["需要你关注或回复的事项1", "事项2"],
  "overview": "今日邮件一句话总览"
}"""


def build_summary_prompt(emails_data: list[dict], date_str: str) -> str:
    # Role & task instruction FIRST, before data
    parts: list[str] = [
        f"你是一位高效的私人秘书。今天是 {date_str}，你收到了 {len(emails_data)} 封邮件。\n"
        "请将这些邮件整理成一份**邮件简报**。\n\n"
        "严格禁止逐封罗列邮件! 不要输出'邮件1/邮件2/邮件3'这种格式。\n"
        "你必须按主题/类型**分类归纳**，用自己的语言提炼关键信息。\n\n"
        f"输出格式: 纯 JSON 对象(不要 Markdown 包裹、不要 ```json 标记), schema 如下:\n\n"
        f"{_EMAIL_JSON_SCHEMA}\n\n"
        "规则:\n"
        "1. categories 按重要程度排序，最需关注的放前面\n"
        "2. summary 是对该类邮件的**整体归纳**(如'本周有3个项目发来了进展汇报，整体进度正常')，绝不是逐封复述\n"
        "3. highlights 提取最值得注意的 2-4 个要点，每个要点是一句完整的话\n"
        "4. attention 列出需要回复或行动的具体事项（没有则为空数组）\n"
        "5. overview 一句话概括今天邮件整体情况\n"
        "6. 通知/广告/订阅类合并总结即可\n"
        "7. 用中文输出\n\n"
        f"═══ 以下是 {len(emails_data)} 封邮件的原始信息 ═══\n",
    ]

    for i, e in enumerate(emails_data, 1):
        parts.append(
            f"[{i}] {e['subject']} | {e['from']} | {e['body_preview'][:120]}"
        )

    parts.append("\n═══ 请直接输出 JSON ═══")
    return "\n".join(parts)


def _extract_json(text: str) -> dict | None:
    """Try to parse a JSON object from LLM output."""
    import json as _json
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()
    idx_s = text.find("{")
    idx_e = text.rfind("}")
    if idx_s != -1 and idx_e > idx_s:
        try:
            obj = _json.loads(text[idx_s:idx_e + 1])
            if isinstance(obj, dict) and "categories" in obj:
                return obj
        except _json.JSONDecodeError:
            pass
    try:
        obj = _json.loads(text)
        if isinstance(obj, dict):
            return obj
    except _json.JSONDecodeError:
        pass
    return None


def _json_to_html(data: dict, date_str: str, email_count: int) -> str:
    """Render structured JSON briefing into HTML matching CSS classes."""
    parts: list[str] = [
        f'<h2 class="es-briefing-title">\U0001f4ec {date_str} \u90ae\u4ef6\u7b80\u62a5'
        f'<span class="es-count">({email_count} \u5c01)</span></h2>'
    ]

    for cat in data.get("categories", []):
        icon = _esc(str(cat.get("icon", "\U0001f4cb")))
        name = _esc(str(cat.get("name", "")))
        summary = _esc(str(cat.get("summary", "")))
        parts.append(f'<div class="es-group">')
        parts.append(f'<h3 class="es-group-title">{icon} {name}</h3>')
        if summary:
            parts.append(f'<p class="es-group-summary">{summary}</p>')
        highlights = cat.get("highlights", [])
        if highlights:
            parts.append('<ul class="es-highlights">')
            for h in highlights:
                parts.append(f'<li>{_esc(str(h))}</li>')
            parts.append('</ul>')
        parts.append('</div>')

    attention = data.get("attention", [])
    if attention:
        parts.append('<div class="es-attention">')
        parts.append('<h3 class="es-attention-title">\u26a0\ufe0f \u9700\u8981\u5173\u6ce8</h3>')
        parts.append('<ul>')
        for a in attention:
            parts.append(f'<li>{_esc(str(a))}</li>')
        parts.append('</ul>')
        parts.append('</div>')

    overview = data.get("overview", "")
    if overview:
        parts.append(f'<div class="es-overview">{_esc(overview)}</div>')

    return "\n".join(parts)


def generate_summary_llm(
    prompt: str,
    model: str,
    api_key: str,
    api_base: str | None = None,
    date_str: str = "",
    email_count: int = 0,
) -> tuple[str, dict | None]:
    """Generate email briefing. Returns (html, items_or_None)."""
    from apps.llm_utils import llm_call
    raw = llm_call(
        messages=[{"role": "user", "content": prompt}],
        model=model, api_key=api_key, api_base=api_base,
        temperature=0.4, max_tokens=1024,
    )
    parsed = _extract_json(raw)
    if parsed:
        html = _json_to_html(parsed, date_str, email_count)
        print("[email_summary] JSON output parsed OK, rendered via template")
        return html, parsed
    print("[email_summary] JSON parse failed, using raw LLM output as HTML")
    return raw, None


def generate_summary_fallback(emails_data: list[dict], date_str: str) -> str:
    """Simple HTML briefing without LLM."""
    parts: list[str] = [
        f'<h2 class="es-briefing-title">\U0001f4ec {date_str} \u90ae\u4ef6\u7b80\u62a5'
        f'<span class="es-count">({len(emails_data)} \u5c01)</span></h2>'
    ]
    parts.append('<div class="es-group">')
    parts.append('<h3 class="es-group-title">\U0001f4cb \u90ae\u4ef6\u6982\u89c8</h3>')
    parts.append(f'<p class="es-group-summary">\u4eca\u65e5\u5171\u6536\u5230 {len(emails_data)} \u5c01\u90ae\u4ef6\u3002</p>')
    parts.append('<ul class="es-highlights">')
    for e in emails_data[:8]:
        parts.append(f'<li><strong>{_esc(e["subject"][:60])}</strong> — {_esc(e["from"][:40])}</li>')
    if len(emails_data) > 8:
        parts.append(f'<li>\u2026\u53e6\u6709 {len(emails_data) - 8} \u5c01</li>')
    parts.append('</ul>')
    parts.append('</div>')
    parts.append(
        f'<div class="es-overview">\u5171 {len(emails_data)} \u5c01\u90ae\u4ef6\u3002'
        '\u5982\u9700\u667a\u80fd\u5206\u7c7b\u548c\u6458\u8981\uff0c\u8bf7\u914d\u7f6e LLM \u6a21\u578b\u3002</div>'
    )
    return "\n".join(parts)


# ── Pipeline ────────────────────────────────────────────────────────

_run_status: dict = {"running": False, "progress": "", "last_run": None, "error": None}


def get_status() -> dict:
    return dict(_run_status)


def run_email_summary(config: dict, model_config: dict | None = None) -> dict:
    """Full pipeline: connect → fetch → summarise → save."""
    global _run_status
    if _run_status["running"]:
        return {"error": "正在运行中"}

    _run_status = {"running": True, "progress": "连接邮箱…", "last_run": None, "error": None}
    date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        _run_status["progress"] = "连接 IMAP…"
        conn = connect_imap(
            config["imap_host"], config.get("imap_port", 993),
            config["imap_user"], config["imap_password"],
            config.get("imap_ssl", True),
        )

        _run_status["progress"] = "获取邮件…"
        emails_data = fetch_recent_emails(
            conn,
            folder=config.get("imap_folder", "INBOX"),
            hours=config.get("hours", 24),
            max_count=config.get("max_emails", 50),
        )
        conn.logout()

        if not emails_data:
            _run_status.update(running=False, progress="完成", last_run=date_str)
            return {"success": True, "email_count": 0, "message": "没有近期邮件"}

        _run_status["progress"] = "生成摘要…"
        has_llm = model_config and model_config.get("model") and model_config.get("api_key")
        items_data: dict | None = None
        if has_llm:
            prompt = build_summary_prompt(emails_data, date_str)
            content, items_data = generate_summary_llm(
                prompt, model_config["model"],
                model_config["api_key"], model_config.get("api_base"),
                date_str=date_str, email_count=len(emails_data),
            )
        else:
            content = generate_summary_fallback(emails_data, date_str)

        report = {
            "date": date_str,
            "email_count": len(emails_data),
            "content": content,
            "generated_at": datetime.now().astimezone().isoformat(),
            "method": "llm" if has_llm else "fallback",
        }
        if items_data is not None:
            report["items"] = items_data
        _save_report(date_str, report)

        _run_status.update(running=False, progress="完成", last_run=date_str, error=None)
        return {"success": True, "email_count": len(emails_data), "date": date_str}

    except Exception as exc:
        print(f"[email_summary] error: {exc}")
        traceback.print_exc()
        _run_status.update(running=False, progress="", error=str(exc))
        return {"error": str(exc)}
