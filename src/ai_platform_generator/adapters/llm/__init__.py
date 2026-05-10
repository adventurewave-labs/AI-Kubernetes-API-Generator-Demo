"""LLM adapters."""

from __future__ import annotations

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog, DemoScenario
from ai_platform_generator.adapters.llm.demo_mode import DemoModeLlmAdapter
from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
from ai_platform_generator.adapters.llm.fallback import FallbackLlmProvider
from ai_platform_generator.adapters.llm.openai_direct import OpenAiLlmAdapter
from ai_platform_generator.adapters.llm.openrouter import OpenRouterLlmAdapter

__version__ = "0.1.0"

__all__ = [
    "DemoCatalog",
    "DemoModeLlmAdapter",
    "DemoScenario",
    "FakeLlmAdapter",
    "FallbackLlmProvider",
    "OpenAiLlmAdapter",
    "OpenRouterLlmAdapter",
    "__version__",
]
