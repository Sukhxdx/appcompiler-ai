"""Stage 3: Schema Generation — produce strict AppConfig from design."""

from __future__ import annotations

import json

from llm.provider import LLMProvider
from schemas.app_config import AppConfig
from schemas.design import SystemDesign

SCHEMA_SYSTEM_PROMPT = """You are a schema generator producing strict executable AppConfig outputs.
Given a system design, return ONLY valid JSON for AppConfig:
{
  "app_name": "string",
  "description": "string",
  "assumptions": ["string"],
  "ui": {"pages": [{"id": "string", "name": "string", "route": "string", "components": [{"id": "string", "type": "form|table|card|chart|nav|button|list", "label": "string", "fields": ["string"], "submit_endpoint": "string|null"}], "allowed_roles": ["string"]}]},
  "api": {"endpoints": [{"id": "string", "path": "string", "method": "string", "description": "string", "request_fields": ["string"], "response_fields": ["string"], "table": "string|null", "allowed_roles": ["string"]}]},
  "database": {"tables": [{"name": "string", "fields": [{"name": "string", "type": "string|integer|float|boolean|datetime|uuid|json", "required": true, "unique": false}], "relations": [{"name": "string", "from_table": "string", "to_table": "string", "type": "string"}]}]},
  "auth": {"enabled": true, "roles": [{"role": "string", "permissions": ["string"], "pages": ["string"], "endpoints": ["string"]}]},
  "business_logic": {"rules": [{"id": "string", "name": "string", "description": "string", "condition": "string", "applies_to_roles": ["string"], "applies_to_entities": ["string"]}]},
  "execution_plan": {"steps": [{"order": 1, "action": "string", "target": "string", "details": "string"}], "estimated_complexity": "low|medium|high"}
}
Every UI form must have submit_endpoint. Every endpoint must reference a database table. No hallucinated entities."""


async def generate_schema(design: SystemDesign, provider: LLMProvider) -> AppConfig:
    payload = design.model_dump()
    payload.pop("source_intent", None)
    user_prompt = json.dumps(payload, indent=2)
    raw = await provider.complete(SCHEMA_SYSTEM_PROMPT, user_prompt)
    data = provider.parse_json(raw)
    if not data.get("assumptions") and design.assumptions:
        data["assumptions"] = design.assumptions
    return AppConfig.model_validate(data)
