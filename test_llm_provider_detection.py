"""Test script for LLM provider auto-detection improvements."""

import sys
from apps.llm_utils import litellm_model_name, LLMCallError

print("=" * 70)
print("LLM Provider Auto-Detection Test")
print("=" * 70)

# Test cases: (model, api_base, expected_result, description)
test_cases = [
    # Case 1: User provides explicit provider prefix - should be respected
    ("ollama/qwen3", "http://localhost:11434/v1", "ollama/qwen3", 
     "Explicit ollama prefix should be preserved"),
    
    ("openai/gpt-4", "http://localhost:11434/v1", "openai/gpt-4",
     "Explicit openai prefix should be preserved"),
    
    # Case 2: Ollama endpoint detection
    ("qwen3", "http://localhost:11434", "ollama/qwen3",
     "localhost:11434 should auto-detect as Ollama"),
    
    ("qwen3", "http://localhost:11434/v1", "ollama/qwen3",
     "localhost:11434/v1 should auto-detect as Ollama"),
    
    ("qwen3", "http://127.0.0.1:11434", "ollama/qwen3",
     "127.0.0.1:11434 should auto-detect as Ollama"),
    
    ("llama3", "http://my-server:8080/ollama/v1", "ollama/llama3",
     "URL with /ollama/ should auto-detect as Ollama"),
    
    # Case 3: Generic OpenAI-compatible endpoints
    ("qwen3", "http://localhost:8000/v1", "openai/qwen3",
     "vLLM-like endpoint should default to openai prefix"),
    
    ("custom-model", "http://api.example.com/v1", "openai/custom-model",
     "Custom endpoint should default to openai prefix"),
    
    # Case 4: No api_base (official providers)
    ("gpt-4", None, "gpt-4",
     "Official OpenAI model without api_base"),
    
    ("claude-3-opus", None, "claude-3-opus",
     "Anthropic model without api_base"),
    
    # Case 5: Already has known prefix
    ("anthropic/claude-3", None, "anthropic/claude-3",
     "Known prefix should be preserved"),
    
    ("gemini/gemini-pro", None, "gemini/gemini-pro",
     "Gemini prefix should be preserved"),
]

print("\nRunning provider detection tests...\n")

passed = 0
failed = 0

for model, api_base, expected, description in test_cases:
    result = litellm_model_name(model, api_base)
    status = "PASS" if result == expected else "FAIL"
    
    if status == "PASS":
        passed += 1
        print(f"[PASS] {description}")
        print(f"  Input:    model='{model}', api_base='{api_base}'")
        print(f"  Result:   '{result}'")
    else:
        failed += 1
        print(f"[FAIL] {description}")
        print(f"  Input:    model='{model}', api_base='{api_base}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
    print()

print("=" * 70)
print(f"Test Results: {passed} passed, {failed} failed")
print("=" * 70)

# Test LLMCallError
print("\n" + "=" * 70)
print("Testing LLMCallError exception wrapper")
print("=" * 70)

try:
    original_error = ValueError("Test error")
    raise LLMCallError(
        "模型调用失败",
        original_error=original_error,
        model="test-model",
        api_base="http://test.com"
    )
except LLMCallError as e:
    print(f"\n[PASS] LLMCallError caught successfully")
    print(f"  Message: {e}")
    print(f"  Context: {e.context}")
    print(f"  Original error: {e.original_error}")

print("\n" + "=" * 70)
print("Pattern Matching Examples")
print("=" * 70)

# Show some edge cases
edge_cases = [
    ("qwen", "http://LOCALHOST:11434/v1", "Case insensitive matching"),
    ("model", "http://server.com:11434", "Port 11434 anywhere"),
    ("model", "https://ollama.example.com/api", "Domain with ollama"),
    ("model", "http://vllm.local:8000", "Non-Ollama local endpoint"),
    ("model", "http://192.168.1.100:11434", "Remote Ollama by IP"),
]

print("\nEdge case handling:\n")
for model, api_base, note in edge_cases:
    result = litellm_model_name(model, api_base)
    print(f"  {note}")
    print(f"    api_base: {api_base}")
    print(f"    result:   {result}")
    print()

if failed == 0:
    print("\n[SUCCESS] All tests passed!")
    sys.exit(0)
else:
    print(f"\n[WARNING] {failed} test(s) failed!")
    sys.exit(1)
