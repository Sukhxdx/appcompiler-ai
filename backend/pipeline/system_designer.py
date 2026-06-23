"""Stage 2: System Design Layer — architecture from intent."""

from __future__ import annotations

import json

from llm.provider import LLMProvider
from schemas.design import SystemDesign
from schemas.intent import IntentExtraction

DESIGN_SYSTEM_PROMPT = """You are a system design architect.
Given structured intent, produce a high-level system design.
Return ONLY valid JSON:
{
  "app_name": "string",
  "description": "string",
  "pages": [{"name": "string", "route": "string", "description": "string", "components": ["string"], "allowed_roles": ["string"]}],
  "endpoints": [{"path": "string", "method": "GET|POST|PUT|PATCH|DELETE", "description": "string", "request_fields": ["string"], "response_fields": ["string"], "table": "string|null", "allowed_roles": ["string"]}],
  "tables": [{"name": "string", "fields": ["string"], "relations": ["string"]}],
  "roles": [{"name": "string", "permissions": ["string"]}],
  "business_rules": [{"name": "string", "description": "string", "applies_to_roles": ["string"], "applies_to_entities": ["string"]}],
  "assumptions": ["string"]
}
Ensure all entities, roles, and features from intent are reflected. Document assumptions."""


async def design_system(intent: IntentExtraction, provider: LLMProvider) -> SystemDesign:
    user_prompt = json.dumps(intent.model_dump(), indent=2)
    raw = await provider.complete(DESIGN_SYSTEM_PROMPT, user_prompt)
    data = provider.parse_json(raw)
    data["raw_prompt"] = intent.raw_prompt or intent.primary_goal
    design = SystemDesign.model_validate(data)
    design.source_intent = intent
    return design
