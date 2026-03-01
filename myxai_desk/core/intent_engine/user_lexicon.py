"""User lexicon & case-key alias management for Intent Engine.

Manages two semantic assets produced by nightly learning:
1. **User lexicon** (synonyms, verb_map, stop_phrases) — consumed by normalizer
2. **Case-key aliases** (alias → canonical) — consumed by case_router

Both support versioning, rollback, and diff for audit/transparency.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

log = logging.getLogger("myxai")

# ── In-memory caches ──────────────────────────────────────────────

_LEXICON_CACHE: dict | None = None
_VERB_MAP_CACHE: dict | None = None
_STOP_PHRASES_CACHE: list | None = None
_ALIAS_CACHE: dict | None = None


# ── User Lexicon ──────────────────────────────────────────────────

def load_user_lexicon() -> tuple[Dict[str, str], Dict[str, str], list[str]]:
    """Load active user lexicon from database.

    Returns (synonyms, verb_map, stop_phrases). Falls back to empty on error.
    """
    global _LEXICON_CACHE, _VERB_MAP_CACHE, _STOP_PHRASES_CACHE
    if _LEXICON_CACHE is not None:
        return _LEXICON_CACHE, _VERB_MAP_CACHE or {}, _STOP_PHRASES_CACHE or []

    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            """SELECT synonyms_json, verb_map_json, stop_phrases_json
               FROM user_lexicon WHERE active = 1
               ORDER BY version DESC LIMIT 1""",
            readonly=True,
        )
        if not rows:
            _LEXICON_CACHE, _VERB_MAP_CACHE, _STOP_PHRASES_CACHE = {}, {}, []
            return {}, {}, []

        row = rows[0]
        s = json.loads(row["synonyms_json"]) if row["synonyms_json"] else {}
        v = json.loads(row["verb_map_json"]) if row["verb_map_json"] else {}
        p = json.loads(row["stop_phrases_json"]) if row["stop_phrases_json"] else []

        _LEXICON_CACHE, _VERB_MAP_CACHE, _STOP_PHRASES_CACHE = s, v, p
        log.debug(f"[lexicon] loaded: {len(s)} synonyms, {len(v)} verbs, {len(p)} stops")
        return s, v, p
    except Exception:
        _LEXICON_CACHE, _VERB_MAP_CACHE, _STOP_PHRASES_CACHE = {}, {}, []
        return {}, {}, []


def reload_lexicon() -> None:
    """Invalidate cache and reload from DB."""
    global _LEXICON_CACHE, _VERB_MAP_CACHE, _STOP_PHRASES_CACHE, _ALIAS_CACHE
    _LEXICON_CACHE = _VERB_MAP_CACHE = _STOP_PHRASES_CACHE = _ALIAS_CACHE = None


def get_synonym(term: str) -> str:
    s, _, _ = load_user_lexicon()
    return s.get(term.lower(), term)


def get_verb_mapping(verb: str) -> str:
    _, v, _ = load_user_lexicon()
    return v.get(verb.lower(), verb)


def save_lexicon(
    synonyms: Dict[str, str],
    verb_map: Dict[str, str],
    stop_phrases: list[str],
    source: str = "nightly_learning",
) -> str | None:
    """Save new versioned lexicon. Deactivates previous versions."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        from myxai_desk.core.intent_engine.dao import init_ie_tables
        init_ie_tables()

        rows = execute(
            "SELECT COALESCE(MAX(version), 0) + 1 as nv FROM user_lexicon",
            readonly=True,
        )
        nv = rows[0]["nv"] if rows else 1
        lid = uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()

        # Deactivate old versions
        execute("UPDATE user_lexicon SET active = 0 WHERE active = 1")

        execute(
            """INSERT INTO user_lexicon
               (id, version, synonyms_json, verb_map_json, stop_phrases_json,
                source, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                lid, nv,
                json.dumps(synonyms, ensure_ascii=False),
                json.dumps(verb_map, ensure_ascii=False),
                json.dumps(stop_phrases, ensure_ascii=False),
                source, now,
            ),
        )
        log.info(f"[lexicon] saved v{nv}: {lid}")
        reload_lexicon()
        return lid
    except Exception:
        log.error("[lexicon] save failed", exc_info=True)
        return None


# ── Lexicon Version Management ────────────────────────────────────

def list_lexicon_versions(limit: int = 20) -> list[dict]:
    """List all lexicon versions (newest first)."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        from myxai_desk.core.intent_engine.dao import init_ie_tables
        init_ie_tables()
        rows = execute(
            """SELECT id, version, source, active, created_at,
                      LENGTH(synonyms_json) as syn_size,
                      LENGTH(verb_map_json) as verb_size,
                      LENGTH(stop_phrases_json) as stop_size
               FROM user_lexicon ORDER BY version DESC LIMIT ?""",
            (limit,), readonly=True,
        )
        result = []
        for r in rows:
            d = dict(r)
            # Count entries without loading full JSON
            try:
                syns = execute(
                    "SELECT synonyms_json FROM user_lexicon WHERE id = ?",
                    (d["id"],), readonly=True,
                )
                if syns and syns[0]["synonyms_json"]:
                    d["synonym_count"] = len(json.loads(syns[0]["synonyms_json"]))
                    d["verb_count"] = len(json.loads(
                        execute("SELECT verb_map_json FROM user_lexicon WHERE id = ?",
                                (d["id"],), readonly=True)[0]["verb_map_json"] or "{}"))
                    d["stop_count"] = len(json.loads(
                        execute("SELECT stop_phrases_json FROM user_lexicon WHERE id = ?",
                                (d["id"],), readonly=True)[0]["stop_phrases_json"] or "[]"))
            except Exception:
                d["synonym_count"] = d["verb_count"] = d["stop_count"] = 0
            result.append(d)
        return result
    except Exception:
        return []


def get_lexicon_detail(version: int | None = None, lexicon_id: str | None = None) -> dict | None:
    """Get full detail of a specific lexicon version."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        if lexicon_id:
            rows = execute("SELECT * FROM user_lexicon WHERE id = ?", (lexicon_id,), readonly=True)
        elif version is not None:
            rows = execute("SELECT * FROM user_lexicon WHERE version = ?", (version,), readonly=True)
        else:
            rows = execute("SELECT * FROM user_lexicon WHERE active = 1 ORDER BY version DESC LIMIT 1", readonly=True)
        if not rows:
            return None
        d = dict(rows[0])
        d["synonyms"] = json.loads(d.pop("synonyms_json", "{}"))
        d["verb_map"] = json.loads(d.pop("verb_map_json", "{}"))
        d["stop_phrases"] = json.loads(d.pop("stop_phrases_json", "[]"))
        return d
    except Exception:
        return None


def rollback_lexicon(target_version: int) -> dict:
    """Rollback to a previous lexicon version.

    Deactivates current version, activates the target version.
    Returns the now-active lexicon detail or error.
    """
    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            "SELECT id FROM user_lexicon WHERE version = ?", (target_version,), readonly=True,
        )
        if not rows:
            return {"error": f"version {target_version} not found"}

        execute("UPDATE user_lexicon SET active = 0 WHERE active = 1")
        execute("UPDATE user_lexicon SET active = 1 WHERE version = ?", (target_version,))
        reload_lexicon()
        log.info(f"[lexicon] rolled back to v{target_version}")
        return get_lexicon_detail(version=target_version) or {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


def diff_lexicon_versions(v1: int, v2: int) -> dict:
    """Compare two lexicon versions. Returns added/removed/changed entries."""
    d1 = get_lexicon_detail(version=v1)
    d2 = get_lexicon_detail(version=v2)
    if not d1 or not d2:
        return {"error": "version not found"}

    result: dict = {"v1": v1, "v2": v2, "diff": {}}
    for field in ("synonyms", "verb_map"):
        old_d = d1.get(field, {})
        new_d = d2.get(field, {})
        added = {k: v for k, v in new_d.items() if k not in old_d}
        removed = {k: v for k, v in old_d.items() if k not in new_d}
        changed = {k: {"old": old_d[k], "new": new_d[k]}
                   for k in old_d if k in new_d and old_d[k] != new_d[k]}
        result["diff"][field] = {"added": added, "removed": removed, "changed": changed}

    old_stops = set(d1.get("stop_phrases", []))
    new_stops = set(d2.get("stop_phrases", []))
    result["diff"]["stop_phrases"] = {
        "added": list(new_stops - old_stops),
        "removed": list(old_stops - new_stops),
    }
    return result


# ── Case-Key Aliases ──────────────────────────────────────────────

def load_alias_map() -> Dict[str, str]:
    """Load active case-key alias map (alias → canonical)."""
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None:
        return _ALIAS_CACHE

    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            "SELECT alias, canonical FROM case_key_alias WHERE active = 1",
            readonly=True,
        )
        _ALIAS_CACHE = {r["alias"]: r["canonical"] for r in rows}
        return _ALIAS_CACHE
    except Exception:
        _ALIAS_CACHE = {}
        return {}


def canonicalize_case_key(case_key: str) -> str:
    """Map a case_key to its canonical form via alias table."""
    aliases = load_alias_map()
    return aliases.get(case_key, case_key)


def save_case_key_aliases(
    clusters: list[dict],
    source: str = "nightly_learning",
) -> int:
    """Save case-key alias mappings from LLM clustering output.

    Args:
        clusters: List of {"canonical": str, "aliases": [str], "confidence": float}
        source: Origin of these aliases

    Returns:
        Number of aliases saved
    """
    count = 0
    try:
        from myxai_desk.core.storage.sqlite import execute
        now = datetime.now(timezone.utc).isoformat()

        for cluster in clusters:
            canonical = cluster.get("canonical", "")
            if not canonical:
                continue
            confidence = min(1.0, max(0.0, float(cluster.get("confidence", 0.8))))
            for alias in cluster.get("aliases", []):
                if not alias or alias == canonical:
                    continue
                aid = uuid4().hex[:16]
                try:
                    execute(
                        """INSERT OR REPLACE INTO case_key_alias
                           (id, alias, canonical, confidence, source, active, created_at)
                           VALUES (?, ?, ?, ?, ?, 1, ?)""",
                        (aid, alias, canonical, confidence, source, now),
                    )
                    count += 1
                except Exception:
                    pass

        global _ALIAS_CACHE
        _ALIAS_CACHE = None
        log.info(f"[lexicon] saved {count} case_key aliases")
    except Exception:
        log.error("[lexicon] save aliases failed", exc_info=True)
    return count


def list_case_key_aliases(limit: int = 50) -> list[dict]:
    """List active case-key aliases."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            """SELECT alias, canonical, confidence, source, created_at
               FROM case_key_alias WHERE active = 1
               ORDER BY created_at DESC LIMIT ?""",
            (limit,), readonly=True,
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_case_key_alias(alias: str) -> bool:
    """Deactivate a single case-key alias."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        execute("UPDATE case_key_alias SET active = 0 WHERE alias = ?", (alias,))
        global _ALIAS_CACHE
        _ALIAS_CACHE = None
        return True
    except Exception:
        return False
