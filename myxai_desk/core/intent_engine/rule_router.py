"""Rule router — matches rules and computes real-valued confidence scores.

Instead of returning a binary 1.0/0.5 confidence, this module evaluates
each rule's base_conf and adjusts it based on textual evidence (paths,
strong verbs, weak phrases, negatives).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from myxai_desk.core.intent_engine.rules import RULES, Rule, RuleMatch

_PATH_PATTERN = re.compile(
    r"[A-Za-z]:\\|/home/|/tmp/|~/|"
    r"\.(?:txt|csv|json|xml|py|js|md|zip|tar|pdf|docx?|xlsx?)\b",
    re.IGNORECASE,
)
_URL_PATTERN = re.compile(r"https?://\S|www\.\S", re.IGNORECASE)

_STRONG_VERB_PATTERN = re.compile(
    r"删除|移动|重命名|压缩|解压|安装|卸载|覆盖|格式化|清空|"
    r"复制|写入|创建|编辑|构建|编译",
    re.IGNORECASE,
)

_PATH_BOOST = 0.12
_STRONG_VERB_BOOST = 0.12
_STRONG_FEATURE_BOOST = 0.10
_WEAK_PENALTY = 0.10
_NEGATIVE_FACTOR = 0.2


@dataclass
class RuleRouteResult:
    """Top rule-based routing decision with scored confidence."""
    category: str
    rule_conf: float
    rule_id: str
    risk_level: str
    all_matches: list[RuleMatch]


def score_rule(rule: Rule, text: str) -> float:
    """Compute a [0, 1] confidence score for a single rule against *text*."""
    conf = rule.base_conf

    if _PATH_PATTERN.search(text) or _URL_PATTERN.search(text):
        conf += _PATH_BOOST
    if _STRONG_VERB_PATTERN.search(text):
        conf += _STRONG_VERB_BOOST
    if rule.strong_features and rule.strong_features.search(text):
        conf += _STRONG_FEATURE_BOOST
    if rule.weak_features and rule.weak_features.search(text):
        conf -= _WEAK_PENALTY

    return max(0.0, min(1.0, conf))


def route(user_text: str) -> RuleRouteResult | None:
    """Run all rules, score each hit, and return the best result.

    Returns ``None`` when no rule matches (caller should fallback to general).
    """
    matches: list[RuleMatch] = []
    seen_cats: set[str] = set()

    for rule in RULES:
        if not rule.pattern.search(user_text):
            continue
        if rule.negative and rule.negative.search(user_text):
            continue
        if rule.category in seen_cats:
            continue
        seen_cats.add(rule.category)

        conf = score_rule(rule, user_text)
        matches.append(RuleMatch(
            rule_id=rule.rule_id,
            category=rule.category,
            priority=rule.priority,
            risk_override=rule.risk_override,
            conf=conf,
        ))

    if not matches:
        return None

    matches.sort(key=lambda h: h.priority, reverse=True)
    best = matches[0]

    from myxai_desk.core.intent_engine.categories import get_risk
    risk = best.risk_override or get_risk(best.category)

    return RuleRouteResult(
        category=best.category,
        rule_conf=best.conf,
        rule_id=best.rule_id,
        risk_level=risk,
        all_matches=matches,
    )
