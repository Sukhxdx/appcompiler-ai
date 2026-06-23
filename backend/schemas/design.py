"""System design layer schema — stage 2 output."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from schemas.intent import IntentExtraction


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ComponentType(str, Enum):
    FORM = "form"
    TABLE = "table"
    CARD = "card"
    CHART = "chart"
    NAV = "nav"
    BUTTON = "button"
    LIST = "list"


class PageDesign(BaseModel):
    name: str
    route: str
    description: str = ""
    components: list[str] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=list)


class EndpointDesign(BaseModel):
    path: str
    method: HttpMethod
    description: str = ""
    request_fields: list[str] = Field(default_factory=list)
    response_fields: list[str] = Field(default_factory=list)
    table: Optional[str] = None
    allowed_roles: list[str] = Field(default_factory=list)


class TableDesign(BaseModel):
    name: str
    fields: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)


class RoleDesign(BaseModel):
    name: str
    permissions: list[str] = Field(default_factory=list)


class BusinessRuleDesign(BaseModel):
    name: str
    description: str
    applies_to_roles: list[str] = Field(default_factory=list)
    applies_to_entities: list[str] = Field(default_factory=list)


class SystemDesign(BaseModel):
    """High-level architecture derived from intent."""

    app_name: str
    description: str
    raw_prompt: str = ""
    pages: list[PageDesign] = Field(default_factory=list)
    endpoints: list[EndpointDesign] = Field(default_factory=list)
    tables: list[TableDesign] = Field(default_factory=list)
    roles: list[RoleDesign] = Field(default_factory=list)
    business_rules: list[BusinessRuleDesign] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_intent: Optional[IntentExtraction] = None

    model_config = {"extra": "forbid"}
