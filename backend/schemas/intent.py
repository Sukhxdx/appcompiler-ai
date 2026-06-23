"""Intent extraction schema — stage 1 output."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AppCategory(str, Enum):
    CRUD = "crud"
    MARKETPLACE = "marketplace"
    DASHBOARD = "dashboard"
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    INTERNAL_TOOL = "internal_tool"
    OTHER = "other"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    MANAGER = "manager"
    CUSTOM = "custom"


class IntentExtraction(BaseModel):
    """Structured intent parsed from natural language requirements."""

    app_name: str = Field(..., min_length=1, description="Proposed application name")
    category: AppCategory = AppCategory.OTHER
    primary_goal: str = Field(..., min_length=1)
    target_users: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    core_features: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    requires_auth: bool = True
    requires_payment: bool = False
    raw_prompt: str = ""

    model_config = {"extra": "forbid"}
