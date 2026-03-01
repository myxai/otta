"""Composite Intent Engine — 组合意图判断器 v0。

核心职责：
    从一次输入中抽取多个意图片段 + 弱顺序关系
    
不负责（交给执行层）：
    - 任务编排执行
    - 失败重试
    - 产物传递
    - 状态管理
    - 交互确认

架构原则：
    Intent Engine 负责**结构化理解**，不负责**任务执行控制**
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 触发组合模式的连接词
_CONNECTORS = re.compile(
    r"然后|再|接着|最后|并且|同时|分别|之后|随后|紧接着|"
    r"then|next|after|finally|and then|followed by",
    re.IGNORECASE,
)

# 强动词（用于判断是否可能是组合任务）
_STRONG_VERBS = re.compile(
    r"搜索|查找|总结|生成|保存|写入|读取|删除|移动|复制|"
    r"安装|重启|发送|翻译|计算|分析|检查|扫描|监控|"
    r"search|summarize|generate|save|write|read|delete|move|"
    r"install|restart|send|translate|calculate|analyze|check|scan",
    re.IGNORECASE,
)

# 大分段标点
_MAJOR_DELIMITERS = re.compile(r"[。；\n]")

# 中分段标点（需要避免误切文件名、URL）
_MINOR_DELIMITERS = re.compile(r"，")

# 弱词（用于合并相邻段）
_WEAK_WORDS = frozenset(["一下", "帮我", "并且", "然后", "再", "接着", "请", "麻烦"])


@dataclass
class IntentSegment:
    """单个意图片段。"""
    id: str
    category: str
    span: tuple[int, int]  # (start, end) in original text
    text: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    matched_rule_id: str = ""
    risk_level: str = "low"


@dataclass
class IntentEdge:
    """意图间的弱依赖关系。"""
    from_id: str
    to_id: str
    edge_type: str = "then"  # then | parallel | optional


@dataclass
class CompositeIntentResult:
    """组合意图判断结果。"""
    mode: str  # "single" | "composite"
    primary_category: str
    intents: list[IntentSegment]
    edges: list[IntentEdge]
    
    # 保持与单步结果兼容
    route_labels: list[str] = field(default_factory=list)
    route_conf: float = 0.0
    allowed_tools: set[str] = field(default_factory=set)
    risk_level: str = "low"


def should_use_composite(text: str) -> bool:
    """判断是否应该使用组合模式。
    
    触发条件（任一命中）：
    1. 包含连接词（然后/再/接着/最后/并且/同时）
    2. 包含标点分段（。；换行，逗号）**加强逗号权重**
    3. 同句内出现 ≥2 个强动词
    4. **新增：逗号分隔且包含强动词**
    """
    # 条件1: 连接词
    if _CONNECTORS.search(text):
        return True
    
    # 条件2: 标点分段
    if _MAJOR_DELIMITERS.search(text):
        return True
    
    # 条件3: 多动词
    verbs = _STRONG_VERBS.findall(text)
    if len(verbs) >= 2:
        return True
    
    # 条件4（新增）：逗号分隔 + 强动词
    # 如果有逗号且至少一个强动词，也触发组合
    if "，" in text or "," in text:
        if len(verbs) >= 1:
            return True
    
    return False


def segment_text(text: str) -> list[tuple[str, int, int]]:
    """将文本分段。
    
    分段策略（改进版）：
    1. 先按 。；换行 断大段
    2. 再按 然后|再|接着|最后|并且 断中段
    3. **改进：更积极使用逗号分段**
    4. 防止误切文件名/URL/数字
    
    Returns:
        List of (segment_text, start_pos, end_pos)
    """
    segments = []
    
    # Step 1: 大分段（。；换行）
    major_parts = _MAJOR_DELIMITERS.split(text)
    current_pos = 0
    
    for part in major_parts:
        if not part.strip():
            current_pos += len(part) + 1
            continue
        
        # Step 2: 按连接词分段
        connector_parts = _CONNECTORS.split(part)
        part_pos = current_pos
        
        for conn_part in connector_parts:
            if not conn_part.strip():
                part_pos += len(conn_part)
                continue
            
            # Step 3: 按逗号分段（改进）
            # 策略：如果逗号两边都有实质内容（>5字符），则分段
            comma_parts = _MINOR_DELIMITERS.split(conn_part)
            conn_pos = part_pos
            
            for i, comma_part in enumerate(comma_parts):
                seg_text = comma_part.strip()
                if not seg_text:
                    conn_pos += len(comma_part) + 1
                    continue
                
                # 找到原始文本中的位置
                start = text.find(seg_text, conn_pos)
                if start == -1:
                    # 如果找不到，可能是因为strip导致，尝试用原始part
                    start = conn_pos
                end = start + len(seg_text)
                
                # 过滤规则：
                # 1. 太短的段（<3字符）跳过
                # 2. 检查是否是文件名的一部分（包含.扩展名）
                # 3. 检查是否是数字（如1,000）
                if len(seg_text) < 3:
                    conn_pos = end + 1
                    continue
                
                # 如果是纯数字或文件扩展名，跳过
                if seg_text.replace(',', '').replace('.', '').isdigit():
                    conn_pos = end + 1
                    continue
                
                # 如果段落看起来是完整的（有动词或关键词），添加
                has_verb = _STRONG_VERBS.search(seg_text)
                is_long_enough = len(seg_text) >= 5
                
                if has_verb or is_long_enough:
                    segments.append((seg_text, start, end))
                
                conn_pos = end + 1
            
            part_pos = conn_pos
        
        current_pos += len(part) + 1
    
    return segments


def merge_adjacent_segments(
    segments: list[IntentSegment],
) -> list[IntentSegment]:
    """合并相邻的相似段落。
    
    合并规则：
    1. 相邻两段 category 相同且置信度都高 (>0.7) → 合并
    2. 第二段是弱词开头 → 吸附到前段
    3. category = general 且很短 (<=4字) → 吸附到相邻高置信段
    """
    if len(segments) <= 1:
        return segments
    
    merged = []
    i = 0
    
    while i < len(segments):
        current = segments[i]
        
        # 检查是否可以与下一段合并
        if i + 1 < len(segments):
            next_seg = segments[i + 1]
            should_merge = False
            
            # 规则1: 相同类别且高置信度
            if (
                current.category == next_seg.category
                and current.confidence > 0.7
                and next_seg.confidence > 0.7
            ):
                should_merge = True
            
            # 规则2: 下一段是弱词
            elif any(next_seg.text.startswith(w) for w in _WEAK_WORDS):
                should_merge = True
            
            # 规则3: 下一段是general且很短
            elif next_seg.category == "general" and len(next_seg.text) <= 4:
                should_merge = True
            
            if should_merge:
                # 合并
                merged_text = f"{current.text} {next_seg.text}"
                merged_seg = IntentSegment(
                    id=current.id,
                    category=current.category,
                    span=(current.span[0], next_seg.span[1]),
                    text=merged_text,
                    confidence=max(current.confidence, next_seg.confidence),
                    entities={**current.entities, **next_seg.entities},
                    matched_rule_id=current.matched_rule_id,
                    risk_level=max(current.risk_level, next_seg.risk_level,
                                   key=lambda r: {"low": 0, "medium": 1, "high": 2}[r]),
                )
                merged.append(merged_seg)
                i += 2  # 跳过下一段
                continue
        
        # 不合并，保留当前段
        merged.append(current)
        i += 1
    
    return merged


def extract_entities(text: str, category: str) -> dict[str, Any]:
    """从文本中提取轻量实体。
    
    只做简单抽取：
    - 文件名/路径
    - topic/keyword
    - format
    """
    entities = {}
    
    # 文件名/路径（对fs类别）
    if category == "fs":
        # 匹配文件名模式
        file_match = re.search(r"(?:保存|写入|导出|另存).*?([^\s，。；]+?\.\w{2,5})", text)
        if file_match:
            entities["path"] = file_match.group(1)
        
        # 匹配目录
        dir_match = re.search(r"(?:目录|文件夹|路径).*?([/\\][\w/\\]+)", text)
        if dir_match:
            entities["directory"] = dir_match.group(1)
    
    # topic（对search/ask类别）
    elif category in ("search", "ask"):
        # 提取引号内的内容或关键名词
        topic_match = re.search(r"[「『""]([^」』""]+)[」』""]", text)
        if topic_match:
            entities["topic"] = topic_match.group(1)
        else:
            # 提取"关于xxx"模式
            about_match = re.search(r"关于(.{2,20}?)(?:的|，|。|$)", text)
            if about_match:
                entities["topic"] = about_match.group(1)
    
    # style（对creative类别）
    elif category == "creative":
        if "总结" in text or "摘要" in text:
            entities["style"] = "summary"
        elif "要点" in text:
            entities["style"] = "key_points"
        elif "详细" in text or "完整" in text:
            entities["style"] = "detailed"
    
    return entities


def create_edges(segments: list[IntentSegment]) -> list[IntentEdge]:
    """生成意图间的弱顺序关系。
    
    策略：
    - 默认按段落顺序 i1→i2→i3
    - 若出现"同时/分别" → parallel
    """
    edges = []
    
    for i in range(len(segments) - 1):
        current = segments[i]
        next_seg = segments[i + 1]
        
        # 检查是否是parallel关系（通过原文判断）
        edge_type = "then"
        # 简单实现：如果段落文本中包含"同时"，标记为parallel
        if "同时" in current.text or "分别" in current.text:
            edge_type = "parallel"
        
        edges.append(IntentEdge(
            from_id=current.id,
            to_id=next_seg.id,
            edge_type=edge_type,
        ))
    
    return edges


def predict_composite(user_text: str) -> CompositeIntentResult:
    """组合意图判断器主入口。
    
    工作流：
    1. 判断是否需要组合模式
    2. 分段
    3. 对每段调用单步判断器
    4. 合并去噪
    5. 生成edges
    6. 返回结构化结果
    """
    from myxai_desk.core.intent_engine.predictor import predict as predict_single
    
    # Step 1: 判断是否需要组合模式
    if not should_use_composite(user_text):
        # 走单步逻辑
        single_result = predict_single(user_text)
        return CompositeIntentResult(
            mode="single",
            primary_category=single_result.route_labels[0] if single_result.route_labels else "general",
            intents=[
                IntentSegment(
                    id="i1",
                    category=single_result.route_labels[0] if single_result.route_labels else "general",
                    span=(0, len(user_text)),
                    text=user_text,
                    confidence=single_result.route_conf,
                    matched_rule_id=single_result.matched_rule_id,
                    risk_level=single_result.risk_level,
                )
            ],
            edges=[],
            route_labels=single_result.route_labels,
            route_conf=single_result.route_conf,
            allowed_tools=single_result.allowed_tools,
            risk_level=single_result.risk_level,
        )
    
    # Step 2: 分段
    text_segments = segment_text(user_text)
    
    # Step 3: 对每段调用单步判断器
    intent_segments = []
    for idx, (seg_text, start, end) in enumerate(text_segments):
        result = predict_single(seg_text)
        
        category = result.route_labels[0] if result.route_labels else "general"
        
        intent_seg = IntentSegment(
            id=f"i{idx+1}",
            category=category,
            span=(start, end),
            text=seg_text,
            confidence=result.route_conf,
            entities=extract_entities(seg_text, category),
            matched_rule_id=result.matched_rule_id,
            risk_level=result.risk_level,
        )
        intent_segments.append(intent_seg)
    
    # Step 4: 合并去噪
    merged_segments = merge_adjacent_segments(intent_segments)
    
    # Step 5: 生成edges
    edges = create_edges(merged_segments)
    
    # Step 6: 确定primary_category（第一个段落的类别）
    primary_category = merged_segments[0].category if merged_segments else "general"
    
    # 收集所有category用于route_labels
    route_labels = [seg.category for seg in merged_segments]
    
    # 收集所有tools
    all_tools = set()
    for seg in merged_segments:
        seg_result = predict_single(seg.text)
        all_tools.update(seg_result.allowed_tools)
    
    # 风险等级取最高
    max_risk = "low"
    for seg in merged_segments:
        if seg.risk_level == "high":
            max_risk = "high"
            break
        elif seg.risk_level == "medium" and max_risk == "low":
            max_risk = "medium"
    
    # 平均置信度
    avg_conf = sum(seg.confidence for seg in merged_segments) / len(merged_segments) if merged_segments else 0.0
    
    return CompositeIntentResult(
        mode="composite",
        primary_category=primary_category,
        intents=merged_segments,
        edges=edges,
        route_labels=route_labels,
        route_conf=round(avg_conf, 4),
        allowed_tools=all_tools,
        risk_level=max_risk,
    )


def format_composite_result(result: CompositeIntentResult) -> dict:
    """将CompositeIntentResult格式化为JSON-friendly dict。"""
    return {
        "mode": result.mode,
        "primary_category": result.primary_category,
        "intents": [
            {
                "id": seg.id,
                "category": seg.category,
                "span": list(seg.span),
                "text": seg.text,
                "confidence": seg.confidence,
                "entities": seg.entities,
                "matched_rule_id": seg.matched_rule_id,
                "risk_level": seg.risk_level,
            }
            for seg in result.intents
        ],
        "edges": [
            {
                "from": edge.from_id,
                "to": edge.to_id,
                "type": edge.edge_type,
            }
            for edge in result.edges
        ],
        "route_labels": result.route_labels,
        "route_conf": result.route_conf,
        "allowed_tools": list(result.allowed_tools),
        "risk_level": result.risk_level,
    }


# =====================================================================
# Monitoring Metrics — composite vs single tracking
# =====================================================================

import threading
from collections import defaultdict


class CompositeMetrics:
    """Thread-safe in-memory metrics collector for composite intent usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0
        self._single = 0
        self._composite = 0
        self._category_counts: dict[str, int] = defaultdict(int)
        self._avg_intents_sum = 0.0
        self._avg_intents_count = 0
        self._edge_type_counts: dict[str, int] = defaultdict(int)
        self._recent: list[dict] = []

    def record(self, result: CompositeIntentResult) -> None:
        with self._lock:
            self._total += 1
            if result.mode == "single":
                self._single += 1
            else:
                self._composite += 1
                self._avg_intents_sum += len(result.intents)
                self._avg_intents_count += 1
                for edge in result.edges:
                    self._edge_type_counts[edge.edge_type] += 1
            for seg in result.intents:
                self._category_counts[seg.category] += 1
            self._recent.append({
                "mode": result.mode,
                "primary": result.primary_category,
                "intents": len(result.intents),
                "conf": round(result.route_conf, 2),
            })
            if len(self._recent) > 100:
                self._recent = self._recent[-100:]

    def snapshot(self) -> dict:
        with self._lock:
            composite_pct = (
                round(self._composite / self._total * 100, 1)
                if self._total > 0 else 0
            )
            avg_intents = (
                round(self._avg_intents_sum / self._avg_intents_count, 2)
                if self._avg_intents_count > 0 else 0
            )
            return {
                "total_requests": self._total,
                "single_count": self._single,
                "composite_count": self._composite,
                "composite_pct": composite_pct,
                "avg_intents_per_composite": avg_intents,
                "category_distribution": dict(self._category_counts),
                "edge_type_distribution": dict(self._edge_type_counts),
                "recent": self._recent[-20:],
            }


_metrics = CompositeMetrics()
