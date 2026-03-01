"""Intent Engine — decision-layer for MyxAI Desk.

Provides intent classification, tool routing, case retrieval,
and plan reuse to reduce LLM search space and improve execution quality.

Components:
- predict: Single-step intent classification
- predict_composite: Composite intent classification (multi-step tasks)
"""

from myxai_desk.core.intent_engine.predictor import predict  # noqa: F401
from myxai_desk.core.intent_engine.composite import (  # noqa: F401
    predict_composite,
    CompositeIntentResult,
    format_composite_result,
)

__all__ = [
    "predict",
    "predict_composite", 
    "CompositeIntentResult",
    "format_composite_result",
]
