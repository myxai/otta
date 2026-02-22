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


def fetch_recent_emails(
    conn,
    folder: str = "INBOX",
    hours: int = 24,
    max_count: int = 50,
) -> list[dict]:
    """Fetch emails from the given time range."""
    conn.select(folder, readonly=True)

    since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
    _, msg_nums = conn.search(None, f'(SINCE "{since_date}")')
    ids = msg_nums[0].split()
    if not ids:
        return []

    ids = ids[-max_count:]
    emails = []
    for mid in ids:
        try:
            _, data = conn.fetch(mid, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            subject = _decode_header(msg["Subject"])
            from_ = _decode_header(msg["From"])
            date_ = msg["Date"] or ""
            body = _extract_body(msg)
            emails.append({
                "subject": subject,
                "from": from_,
                "date": date_,
                "body_preview": body,
            })
        except Exception:
            continue

    emails.reverse()
    return emails


# ── Summary generation ──────────────────────────────────────────────

def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_summary_prompt(emails_data: list[dict], date_str: str) -> str:
    lines = [f"以下是 {date_str} 收到的 {len(emails_data)} 封邮件摘要信息：\n"]
    for i, e in enumerate(emails_data, 1):
        lines.append(f"[{i}] 主题: {e['subject']}")
        lines.append(f"    发件人: {e['from']}")
        lines.append(f"    日期: {e['date']}")
        lines.append(f"    预览: {e['body_preview'][:200]}\n")

    lines.append(
        "\n请生成一份简洁的邮件摘要报告（纯 HTML 片段，不含 <html>/<body> 标签）。\n"
        "要求：\n"
        "- 按重要程度分组：重要邮件、普通邮件、通知/广告\n"
        "- 每封邮件一行：主题 + 发件人 + 一句话摘要\n"
        "- 使用以下 CSS class：\n"
        "  - es-group: 分组容器\n"
        "  - es-group-title: 分组标题\n"
        "  - es-item: 单封邮件\n"
        "  - es-subject: 主题\n"
        "  - es-from: 发件人\n"
        "  - es-summary: 一句话摘要\n"
        "- 末尾加一段 es-overview 总结今日邮件概况\n"
    )
    return "\n".join(lines)


def generate_summary_llm(
    prompt: str,
    model: str,
    api_key: str,
    api_base: str | None = None,
) -> str:
    from apps.llm_utils import llm_call
    return llm_call(
        messages=[{"role": "user", "content": prompt}],
        model=model, api_key=api_key, api_base=api_base,
        temperature=0.4, max_tokens=2048,
    )


def generate_summary_fallback(emails_data: list[dict], date_str: str) -> str:
    """Simple HTML summary without LLM."""
    items = []
    for e in emails_data:
        items.append(
            f'<div class="es-item">'
            f'<span class="es-subject">{_esc(e["subject"])}</span>'
            f'<span class="es-from">{_esc(e["from"])}</span>'
            f'<span class="es-summary">{_esc(e["body_preview"][:100])}</span>'
            f'</div>'
        )
    return (
        f'<div class="es-group">'
        f'<h3 class="es-group-title">邮件列表 ({len(emails_data)} 封)</h3>'
        + "\n".join(items)
        + '</div>'
        + f'<div class="es-overview">共 {len(emails_data)} 封邮件。'
        + '如需智能分组和摘要，请配置 LLM 模型。</div>'
    )


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
        if has_llm:
            prompt = build_summary_prompt(emails_data, date_str)
            content = generate_summary_llm(
                prompt, model_config["model"],
                model_config["api_key"], model_config.get("api_base"),
            )
        else:
            content = generate_summary_fallback(emails_data, date_str)

        report = {
            "date": date_str,
            "email_count": len(emails_data),
            "content": content,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "llm" if has_llm else "fallback",
        }
        _save_report(date_str, report)

        _run_status.update(running=False, progress="完成", last_run=date_str, error=None)
        return {"success": True, "email_count": len(emails_data), "date": date_str}

    except Exception as exc:
        print(f"[email_summary] error: {exc}")
        traceback.print_exc()
        _run_status.update(running=False, progress="", error=str(exc))
        return {"error": str(exc)}
