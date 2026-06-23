"""Deterministic mock LLM — no API key required."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from llm.mock_generator import build_design_dict, build_intent_dict, build_schema_dict, analyze_prompt
from llm.provider import LLMProvider


class MockLLMProvider(LLMProvider):
    """Rule-based mock that returns structured JSON for pipeline stages."""

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        stage = self._detect_stage(system_prompt)
        data = self._generate(stage, user_prompt)
        return json.dumps(data, indent=2)

    def _detect_stage(self, system_prompt: str) -> str:
        lower = system_prompt.lower()
        if "schema generator" in lower or "appconfig" in lower:
            return "schema"
        if "system design" in lower or "design architect" in lower:
            return "design"
        if "intent extraction" in lower or "extract structured intent" in lower:
            return "intent"
        return "generic"

    def _parse_context(self, user_prompt: str) -> dict[str, Any]:
        try:
            data = json.loads(user_prompt)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {}

    def _resolve_prompt(self, stage: str, user_prompt: str) -> str:
        ctx = self._parse_context(user_prompt)
        if stage == "intent":
            return user_prompt
        # Prefer original NL prompt stored on intent; never analyze design JSON text.
        return ctx.get("raw_prompt") or user_prompt

    def _generate(self, stage: str, user_prompt: str) -> dict[str, Any]:
        ctx = self._parse_context(user_prompt)
        prompt_text = self._resolve_prompt(stage, user_prompt)
        app_name = ctx.get("app_name")
        profile = analyze_prompt(prompt_text, app_name)

        if stage == "intent":
            data = build_intent_dict(profile)
            data["raw_prompt"] = prompt_text
            return data
        if stage == "design":
            return build_design_dict(profile)
        if stage == "schema":
            return build_schema_dict(profile)
        return build_schema_dict(profile)
