"""Stage 1: Intent Extraction — parse NL requirements into structured intent."""

from __future__ import annotations

import json

from llm.provider import LLMProvider
from schemas.intent import IntentExtraction

INTENT_SYSTEM_PROMPT = """You are an intent extraction engine for application requirements.
Extract structured intent from the user's natural language prompt.
Return ONLY valid JSON matching this intent schema:
{
  "app_name": "string",
  "category": "crud|marketplace|dashboard|social|ecommerce|internal_tool|other",
  "primary_goal": "string",
  "target_users": ["string"],
  "roles": ["string"],
  "core_features": ["string"],
  "entities": ["string"],
  "constraints": ["string"],
  "ambiguities": ["string"],
  "requires_auth": true,
  "requires_payment": false
}
Identify ambiguities, conflicts, and missing information explicitly."""


async def extract_intent(prompt: str, provider: LLMProvider) -> IntentExtraction:
    raw = await provider.complete(INTENT_SYSTEM_PROMPT, prompt)
    data = provider.parse_json(raw)
    data["raw_prompt"] = prompt
    return IntentExtraction.model_validate(data)
