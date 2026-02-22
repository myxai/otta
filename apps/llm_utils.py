"""Shared LLM call utility for all apps."""

import os

_KNOWN_LITELLM_PREFIXES = (
    "openai/", "azure/", "anthropic/", "bedrock/", "vertex_ai/",
    "cohere/", "huggingface/", "ollama/", "deepseek/", "groq/",
    "together_ai/", "openrouter/", "gemini/", "mistral/",
)


def litellm_model_name(model: str, api_base: str | None) -> str:
    """Ensure *model* has a provider prefix that litellm understands."""
    if any(model.startswith(p) for p in _KNOWN_LITELLM_PREFIXES):
        return model
    if api_base:
        return f"openai/{model}"
    return model


def llm_call(
    messages: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> str:
    """Thin wrapper around litellm.completion with auto provider detection."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    resolved = litellm_model_name(model, api_base)
    resp = litellm.completion(
        model=resolved,
        messages=messages,
        api_key=api_key,
        api_base=api_base,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""
