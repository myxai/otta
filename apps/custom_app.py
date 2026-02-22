"""Custom App framework — user-defined apps powered by the nanobot Agent.

Users create apps by providing a prompt template with {{parameter}} placeholders.
Each run substitutes parameters, sends the prompt through the full nanobot Agent
loop (with MCP tools, web search, etc.), and saves the result as a report.

After the first successful run, users can "confirm" the result. The system then
uses the LLM to analyse the successful output and auto-generate an
**enhanced_prompt** — a set of execution constraints (format, tools, structure)
that gets appended to every subsequent run for higher consistency.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

_BASE_DIR = Path.home() / ".nanobot" / "apps" / "custom"
_PARAM_RE = re.compile(r"\{\{(\w+)\}\}")


# ── Persistence helpers ─────────────────────────────────────────────

def _ensure_dirs(app_id: str | None = None):
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    if app_id:
        (_BASE_DIR / app_id / "reports").mkdir(parents=True, exist_ok=True)


def _app_file(app_id: str) -> Path:
    return _BASE_DIR / f"{app_id}.json"


def _reports_dir(app_id: str) -> Path:
    return _BASE_DIR / app_id / "reports"


# ── CRUD ────────────────────────────────────────────────────────────

def create_app(
    name: str,
    prompt_template: str,
    parameters: list[dict] | None = None,
    icon: str = "🤖",
    schedule: dict | None = None,
    source: dict | None = None,
) -> dict:
    """Create a new custom app. Returns the app definition."""
    _ensure_dirs()
    app_id = "capp_" + uuid.uuid4().hex[:10]

    if parameters is None:
        parameters = extract_parameters(prompt_template)

    app = {
        "id": app_id,
        "name": name,
        "icon": icon,
        "prompt_template": prompt_template,
        "parameters": parameters,
        "schedule": schedule or {"time": "", "enabled": False},
        "source": source or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
    }
    _app_file(app_id).write_text(
        json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return app


def update_app(app_id: str, **kwargs) -> dict | None:
    """Update fields on an existing custom app."""
    app = get_app(app_id)
    if not app:
        return None
    for key in ("name", "icon", "prompt_template", "parameters", "schedule",
                "enhanced_prompt", "reference_run"):
        if key in kwargs:
            app[key] = kwargs[key]
    if "prompt_template" in kwargs and "parameters" not in kwargs:
        app["parameters"] = extract_parameters(kwargs["prompt_template"])
    _app_file(app_id).write_text(
        json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return app


def delete_app(app_id: str) -> bool:
    fp = _app_file(app_id)
    if not fp.exists():
        return False
    fp.unlink()
    reports_dir = _BASE_DIR / app_id
    if reports_dir.exists():
        import shutil
        shutil.rmtree(reports_dir, ignore_errors=True)
    return True


def list_apps() -> list[dict]:
    _ensure_dirs()
    apps = []
    for fp in _BASE_DIR.glob("capp_*.json"):
        try:
            apps.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    apps.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return apps


def get_app(app_id: str) -> dict | None:
    fp = _app_file(app_id)
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def set_last_run(app_id: str, ts: str | None = None):
    app = get_app(app_id)
    if not app:
        return
    app["last_run"] = ts or datetime.now(timezone.utc).isoformat()
    _app_file(app_id).write_text(
        json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8",
    )


# ── Template & parameters ──────────────────────────────────────────

def extract_parameters(template: str) -> list[dict]:
    """Parse {{var}} placeholders from a template and return parameter defs."""
    seen = set()
    params = []
    for m in _PARAM_RE.finditer(template):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        params.append({
            "name": name,
            "label": name,
            "type": "text",
            "default": "",
        })
    return params


def fill_template(template: str, param_values: dict) -> str:
    """Replace {{var}} placeholders with actual values."""
    def _repl(m):
        name = m.group(1)
        return str(param_values.get(name, m.group(0)))
    return _PARAM_RE.sub(_repl, template)


# ── Enhanced prompt generation ──────────────────────────────────────

_ENHANCE_SYSTEM = """你是一个 prompt 工程专家。用户有一个自动化任务的 prompt 模板，并且已经确认了一次成功的执行结果。
请根据原始 prompt 和成功输出，生成一段**执行约束指令**，使后续执行能保持一致的质量和格式。

要求：
1. 分析成功输出的格式（HTML/Markdown/纯文本/JSON等）、结构（标题、分节、列表等）、长度特征
2. 分析成功执行使用的工具，明确哪些工具是必须使用的
3. 生成简洁明确的约束指令，包括：
   - 输出格式要求（必须用什么格式）
   - 结构要求（必须包含哪些部分）
   - 质量要求（内容长度下限、信息来源要求等）
   - 工具使用要求（如果使用了搜索/浏览器等工具，明确要求使用）
4. 只输出约束指令本身，不要解释，不要包裹在代码块中
5. 用中文输出（除非原始 prompt 是英文的）"""


def generate_enhanced_prompt(
    original_template: str,
    successful_output: str,
    tools_used: list[str],
    model: str,
    api_key: str,
    api_base: str | None = None,
) -> str:
    """Use LLM to analyse a confirmed-good execution and produce constraints."""
    from apps.llm_utils import llm_call

    tools_str = ", ".join(tools_used) if tools_used else "（无工具调用）"
    output_preview = successful_output[:3000]

    user_msg = (
        f"## 原始 Prompt 模板\n{original_template}\n\n"
        f"## 成功执行使用的工具\n{tools_str}\n\n"
        f"## 成功执行的输出（截取前3000字）\n{output_preview}"
    )

    return llm_call(
        messages=[
            {"role": "system", "content": _ENHANCE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.3,
        max_tokens=1024,
    ).strip()


def build_effective_prompt(app: dict, param_values: dict) -> str:
    """Build the final prompt: filled template + enhanced constraints (if any)."""
    prompt = fill_template(app["prompt_template"], param_values)
    enhanced = app.get("enhanced_prompt", "")
    if enhanced:
        prompt += "\n\n---\n【执行要求】\n" + enhanced
    return prompt


# ── Reports ─────────────────────────────────────────────────────────

def save_report(
    app_id: str,
    content: str,
    params_used: dict,
    tools_used: list[str] | None = None,
) -> dict:
    _ensure_dirs(app_id)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    report = {
        "date": date_str,
        "content": content,
        "params_used": params_used,
        "tools_used": tools_used or [],
        "generated_at": now.isoformat(),
    }
    (_reports_dir(app_id) / f"{date_str}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return report


def list_reports(app_id: str) -> list[dict]:
    d = _reports_dir(app_id)
    if not d.exists():
        return []
    reports = []
    for fp in sorted(d.glob("*.json"), reverse=True):
        try:
            meta = json.loads(fp.read_text(encoding="utf-8"))
            reports.append({
                "date": meta.get("date", fp.stem),
                "generated_at": meta.get("generated_at", ""),
                "tools_used": meta.get("tools_used", []),
            })
        except Exception:
            pass
    return reports


def get_report(app_id: str, date_str: str) -> dict | None:
    fp = _reports_dir(app_id) / f"{date_str}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
