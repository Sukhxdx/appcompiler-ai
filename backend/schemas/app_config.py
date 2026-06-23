"""Final executable application configuration schema — stage 3+ output."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UUID = "uuid"
    JSON = "json"


class UIComponent(BaseModel):
    id: str
    type: str
    label: str = ""
    fields: list[str] = Field(default_factory=list)
    submit_endpoint: Optional[str] = None
    props: dict[str, Any] = Field(default_factory=dict)


class UIPage(BaseModel):
    id: str
    name: str
    route: str
    components: list[UIComponent] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=list)


class UILayer(BaseModel):
    pages: list[UIPage] = Field(default_factory=list)


class APIEndpoint(BaseModel):
    id: str
    path: str
    method: str
    description: str = ""
    request_fields: list[str] = Field(default_factory=list)
    response_fields: list[str] = Field(default_factory=list)
    table: Optional[str] = None
    allowed_roles: list[str] = Field(default_factory=list)


class APILayer(BaseModel):
    endpoints: list[APIEndpoint] = Field(default_factory=list)


class DBField(BaseModel):
    name: str
    type: FieldType = FieldType.STRING
    required: bool = True
    unique: bool = False
    default: Optional[Any] = None


class DBRelation(BaseModel):
    name: str
    from_table: str
    to_table: str
    type: str = "one_to_many"


class DBTable(BaseModel):
    name: str
    fields: list[DBField] = Field(default_factory=list)
    relations: list[DBRelation] = Field(default_factory=list)


class DatabaseLayer(BaseModel):
    tables: list[DBTable] = Field(default_factory=list)


class RolePermission(BaseModel):
    role: str
    permissions: list[str] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)


class AuthLayer(BaseModel):
    enabled: bool = True
    roles: list[RolePermission] = Field(default_factory=list)


class BusinessRule(BaseModel):
    id: str
    name: str
    description: str
    condition: str = ""
    applies_to_roles: list[str] = Field(default_factory=list)
    applies_to_entities: list[str] = Field(default_factory=list)


class BusinessLogicLayer(BaseModel):
    rules: list[BusinessRule] = Field(default_factory=list)


class ExecutionStep(BaseModel):
    order: int
    action: str
    target: str
    details: str = ""


class ExecutionPlan(BaseModel):
    steps: list[ExecutionStep] = Field(default_factory=list)
    estimated_complexity: str = "medium"


class ValidationIssue(BaseModel):
    layer: str
    severity: str  # error | warning | info
    code: str
    message: str
    field: Optional[str] = None
    entity: Optional[str] = None


class ValidationReport(BaseModel):
    valid: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)
    repaired_layers: list[str] = Field(default_factory=list)
    repair_count: int = 0
    clarification_needed: bool = False
    clarification_notes: list[str] = Field(default_factory=list)


class RuntimeSimulationResult(BaseModel):
    executable: bool = False
    checks: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Strict validated executable application configuration."""

    app_name: str
    description: str
    assumptions: list[str] = Field(default_factory=list)
    ui: UILayer = Field(default_factory=UILayer)
    api: APILayer = Field(default_factory=APILayer)
    database: DatabaseLayer = Field(default_factory=DatabaseLayer)
    auth: AuthLayer = Field(default_factory=AuthLayer)
    business_logic: BusinessLogicLayer = Field(default_factory=BusinessLogicLayer)
    execution_plan: ExecutionPlan = Field(default_factory=ExecutionPlan)
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    runtime: Optional[RuntimeSimulationResult] = None

    model_config = {"extra": "forbid"}
