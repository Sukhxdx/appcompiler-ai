"""LLM provider abstraction for OpenAI, Gemini, and mock mode."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMProvider(ABC):
    """Abstract base for LLM completions."""

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw text completion from the model."""

    def parse_json(self, text: str) -> dict[str, Any]:
        """Extract JSON object from model response."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}...")


def get_provider() -> LLMProvider:
    """Factory: LLM_PROVIDER env var = mock | openai | gemini."""
    from llm.mock_provider import MockLLMProvider

    provider_name = os.getenv("LLM_PROVIDER", "mock").lower()

    if provider_name == "openai":
        from llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider_name == "gemini":
        from llm.gemini_provider import GeminiProvider

        return GeminiProvider()
    return MockLLMProvider()
