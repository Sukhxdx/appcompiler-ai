"""Stage 5: Repair Engine — fix only broken layers."""

from __future__ import annotations

import copy
from typing import Literal

from schemas.app_config import (
    APIEndpoint,
    AppConfig,
    DBField,
    DBTable,
    FieldType,
    RolePermission,
    UIComponent,
    UIPage,
    ValidationIssue,
    ValidationReport,
)
from pipeline.validator import validate_config
from pipeline.endpoint_utils import endpoints_for_role_from_config

LayerName = Literal["api", "ui", "database", "auth", "business_logic", "root"]


def _issues_by_layer(report: ValidationReport) -> dict[str, list[ValidationIssue]]:
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in report.issues:
        if issue.severity != "error":
            continue
        grouped.setdefault(issue.layer, []).append(issue)
    return grouped


def _next_ep_id(config: AppConfig) -> str:
    return f"ep_{len(config.api.endpoints)}"


def _default_field_type(name: str) -> FieldType:
    if name in ("id",) or name.endswith("_id"):
        return FieldType.UUID
    if name in ("created_at", "updated_at"):
        return FieldType.DATETIME
    if any(x in name for x in ("count", "amount", "total", "rate")):
        return FieldType.INTEGER
    return FieldType.STRING


def _dashboard_metrics(config: AppConfig) -> list[str]:
    if any(t.name == "tasks" for t in config.database.tables):
        return ["total_tasks", "completed_tasks", "pending_tasks", "active_users"]
    if any(t.name == "contacts" for t in config.database.tables):
        return ["total_contacts", "new_leads", "active_users"]
    return ["active_users", "total_records", "growth_rate"]


def _repair_database(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    table_map = {t.name: t for t in config.database.tables}

    for issue in issues:
        if issue.code == "UNKNOWN_DB_FIELD" and issue.field and issue.entity:
            ep = next((e for e in config.api.endpoints if e.id == issue.entity), None)
            if ep and ep.table and ep.table in table_map:
                table = table_map[ep.table]
                if issue.field not in {f.name for f in table.fields}:
                    table.fields.append(DBField(name=issue.field, type=_default_field_type(issue.field), required=False))
                    assumptions.append(f"[repair:database] Added missing field '{issue.field}' to table '{ep.table}'")

        if issue.code == "MISSING_PAYMENTS_INFRA":
            if not any(t.name == "subscriptions" for t in config.database.tables):
                config.database.tables.append(
                    DBTable(
                        name="subscriptions",
                        fields=[
                            DBField(name="id", type=FieldType.UUID, required=True, unique=True),
                            DBField(name="user_id", type=FieldType.UUID, required=True),
                            DBField(name="plan", type=FieldType.STRING, required=True),
                            DBField(name="status", type=FieldType.STRING, required=True),
                            DBField(name="amount", type=FieldType.INTEGER, required=False),
                        ],
                    )
                )
                assumptions.append("[repair:database] Added subscriptions table for payments/premium")
            if not any(t.name == "payments" for t in config.database.tables):
                config.database.tables.append(
                    DBTable(
                        name="payments",
                        fields=[
                            DBField(name="id", type=FieldType.UUID, required=True, unique=True),
                            DBField(name="user_id", type=FieldType.UUID, required=True),
                            DBField(name="amount", type=FieldType.INTEGER, required=True),
                            DBField(name="status", type=FieldType.STRING, required=True),
                        ],
                    )
                )
                assumptions.append("[repair:database] Added payments table")

        if issue.code in ("MISSING_ASSIGNEE_FIELD", "MISSING_ASSIGNEE_RELATION") and issue.entity == "tasks":
            tasks = table_map.get("tasks")
            if tasks:
                if issue.code == "MISSING_ASSIGNEE_FIELD" or not any(f.name == "assignee_id" for f in tasks.fields):
                    if not any(f.name == "assignee_id" for f in tasks.fields):
                        tasks.fields.append(DBField(name="assignee_id", type=FieldType.UUID, required=False))
                        assumptions.append("[repair:database] Added assignee_id to tasks table")
                if issue.code == "MISSING_ASSIGNEE_RELATION" or not any(
                    "assignee" in r.name.lower() for r in tasks.relations
                ):
                    from schemas.app_config import DBRelation

                    if not any("assignee" in r.name.lower() for r in tasks.relations):
                        tasks.relations.append(
                            DBRelation(name="task_assignee", from_table="tasks", to_table="users", type="many_to_one")
                        )
                        assumptions.append("[repair:database] Added tasks.assignee_id -> users.id relation")

    return config, assumptions


def _repair_api(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    tables = {t.name for t in config.database.tables}
    existing_paths = {(e.path, e.method) for e in config.api.endpoints}

    for issue in issues:
        if issue.code == "UNKNOWN_TABLE" and issue.entity:
            ep = next((e for e in config.api.endpoints if e.id == issue.entity), None)
            if ep and ep.table and ep.table not in tables:
                config.database.tables.append(
                    DBTable(name=ep.table, fields=[DBField(name="id", type=FieldType.UUID, required=True, unique=True)])
                )
                tables.add(ep.table)
                assumptions.append(f"[repair:api] Created table '{ep.table}' for endpoint '{ep.path}'")

        if issue.code == "UNKNOWN_DB_FIELD" and issue.field and issue.entity:
            ep = next((e for e in config.api.endpoints if e.id == issue.entity), None)
            if ep and ep.table:
                table = next((t for t in config.database.tables if t.name == ep.table), None)
                if table and issue.field not in {f.name for f in table.fields}:
                    table.fields.append(
                        DBField(name=issue.field, type=_default_field_type(issue.field), required=False)
                    )
                    assumptions.append(f"[repair:api] Added missing DB field '{issue.field}' to table '{ep.table}'")

        if issue.code == "MISSING_USERS_LIST_API" and ("GET", "/api/users") not in {(e.method, e.path) for e in config.api.endpoints}:
            config.api.endpoints.append(
                APIEndpoint(
                    id=_next_ep_id(config),
                    path="/api/users",
                    method="GET",
                    description="List users (admin)",
                    response_fields=["id", "email", "role"],
                    table="users",
                    allowed_roles=["admin"],
                )
            )
            assumptions.append("[repair:api] Added GET /api/users for admin user management")

        if issue.code == "TABLE_NO_GET_ENDPOINT" and issue.field:
            path = issue.field
            if (path, "GET") not in existing_paths:
                table = "tasks" if "task" in path else "contacts" if "contact" in path else "users" if "user" in path else None
                config.api.endpoints.append(
                    APIEndpoint(
                        id=_next_ep_id(config),
                        path=path,
                        method="GET",
                        description=f"List resource for {path}",
                        response_fields=["id"],
                        table=table,
                        allowed_roles=["admin", "user"],
                    )
                )
                existing_paths.add((path, "GET"))
                assumptions.append(f"[repair:api] Added GET endpoint '{path}' for table component")

    return config, assumptions


def _repair_ui(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    endpoint_paths = [e.path for e in config.api.endpoints]

    for issue in issues:
        if issue.code == "UNKNOWN_ENDPOINT" and issue.entity:
            for page in config.ui.pages:
                for comp in page.components:
                    if comp.id == issue.entity:
                        if comp.type == "form" and comp.submit_endpoint:
                            fallback = next((e.path for e in config.api.endpoints if e.method == "POST"), endpoint_paths[0] if endpoint_paths else "/api/auth/login")
                            assumptions.append(f"[repair:ui] Remapped form '{comp.id}' submit_endpoint to '{fallback}'")
                            comp.submit_endpoint = fallback
                        if comp.type == "table":
                            fallback = next((e.path for e in config.api.endpoints if e.method == "GET"), "/api/tasks")
                            comp.props["data_endpoint"] = fallback
                            assumptions.append(f"[repair:ui] Set table '{comp.id}' data_endpoint to '{fallback}'")

        if issue.code == "DASHBOARD_LOGIN_FIELDS" and issue.entity:
            metrics = _dashboard_metrics(config)
            for page in config.ui.pages:
                for comp in page.components:
                    if comp.id == issue.entity:
                        comp.fields = metrics
                        comp.props["data_endpoint"] = comp.props.get("data_endpoint") or "/api/analytics/summary"
                        assumptions.append(f"[repair:ui] Replaced login fields on dashboard card '{comp.id}' with metrics {metrics}")

        if issue.code == "TABLE_NO_GET_ENDPOINT" and issue.entity:
            for page in config.ui.pages:
                for comp in page.components:
                    if comp.id == issue.entity:
                        guess = "/api/tasks" if any(t.name == "tasks" for t in config.database.tables) else "/api/contacts" if any(t.name == "contacts" for t in config.database.tables) else "/api/users"
                        comp.props["data_endpoint"] = guess
                        assumptions.append(f"[repair:ui] Assigned data_endpoint '{guess}' to table '{comp.id}'")

        if issue.code == "MISSING_ADMIN_USERS_PAGE":
            if not any(p.route == "/admin/users" for p in config.ui.pages):
                config.ui.pages.append(
                    UIPage(
                        id="admin_users",
                        name="User Management",
                        route="/admin/users",
                        allowed_roles=["admin"],
                        components=[
                            UIComponent(
                                id="admin_users_table",
                                type="table",
                                label="Users",
                                fields=["id", "email", "role"],
                                props={"data_endpoint": "/api/users"},
                            ),
                            UIComponent(
                                id="admin_user_edit_form",
                                type="form",
                                label="Edit User",
                                fields=["email", "role"],
                                submit_endpoint="/api/users/{id}",
                                props={"method": "PUT"},
                            ),
                        ],
                    )
                )
                assumptions.append("[repair:ui] Added /admin/users page with users_table for admin role")

        if issue.code == "ADMIN_PAGE_WRONG_ROLE" and issue.entity:
            page = next((p for p in config.ui.pages if p.id == issue.entity), None)
            if page:
                page.allowed_roles = ["admin"]
                assumptions.append(f"[repair:ui] Restricted page '{page.name}' to admin role")

        if issue.code == "FORM_NO_ENDPOINT" and issue.entity:
            for page in config.ui.pages:
                for comp in page.components:
                    if comp.id == issue.entity:
                        comp.submit_endpoint = next((e.path for e in config.api.endpoints if e.method == "POST"), "/api/tasks")
                        assumptions.append(f"[repair:ui] Added submit_endpoint to form '{comp.id}'")

    return config, assumptions


def _repair_auth(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    pages = {p.route for p in config.ui.pages}
    endpoints = {e.path for e in config.api.endpoints}

    for issue in issues:
        if issue.code == "UNKNOWN_PAGE" and issue.entity and issue.field:
            for rp in config.auth.roles:
                if rp.role == issue.entity and issue.field in rp.pages:
                    rp.pages = [p for p in rp.pages if p != issue.field]
                    assumptions.append(f"[repair:auth] Removed unknown page '{issue.field}' from role '{rp.role}'")
        if issue.code == "UNKNOWN_ENDPOINT" and issue.entity and issue.field:
            for rp in config.auth.roles:
                if rp.role == issue.entity and issue.field in rp.endpoints:
                    rp.endpoints = [e for e in rp.endpoints if e != issue.field]
                    assumptions.append(f"[repair:auth] Removed unknown endpoint '{issue.field}' from role '{rp.role}'")
        if issue.code == "NO_ROLES":
            config.auth.roles.append(
                RolePermission(role="user", permissions=["read"], pages=list(pages)[:1], endpoints=list(endpoints)[:1])
            )
            assumptions.append("[repair:auth] Added default user role")

    # Sync role endpoint permissions (method-aware, deduplicated)
    for role_name in ("admin", "user", "guest"):
        rp = next((r for r in config.auth.roles if r.role == role_name), None)
        if rp:
            rp.endpoints = endpoints_for_role_from_config(config, [role_name])

    return config, assumptions


def _repair_business_logic(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    roles = {r.role for r in config.auth.roles}
    entities = {t.name for t in config.database.tables}

    for issue in issues:
        if issue.code == "MISSING_ASSIGNEE_RULE":
            from schemas.app_config import BusinessRule

            if not any(r.name == "valid_task_assignee" for r in config.business_logic.rules):
                config.business_logic.rules.append(
                    BusinessRule(
                        id="rule_valid_assignee",
                        name="valid_task_assignee",
                        description="Task assignee must reference an existing user.",
                        condition="assignee_id exists in users.id",
                        applies_to_roles=["user", "admin"],
                        applies_to_entities=["tasks", "users"],
                    )
                )
                assumptions.append("[repair:business_logic] Added valid_task_assignee validation rule")
        if issue.code == "UNKNOWN_ROLE" and issue.entity:
            rule = next((r for r in config.business_logic.rules if r.id == issue.entity), None)
            if rule and issue.field:
                rule.applies_to_roles = [r for r in rule.applies_to_roles if r in roles]
                assumptions.append(f"[repair:business_logic] Pruned unknown role '{issue.field}' from rule '{rule.name}'")
        if issue.code == "UNKNOWN_ENTITY" and issue.entity:
            rule = next((r for r in config.business_logic.rules if r.id == issue.entity), None)
            if rule and issue.field:
                rule.applies_to_entities = [e for e in rule.applies_to_entities if e in entities]
                assumptions.append(f"[repair:business_logic] Pruned unknown entity '{issue.field}' from rule '{rule.name}'")
    return config, assumptions


def _repair_root(config: AppConfig, issues: list[ValidationIssue]) -> tuple[AppConfig, list[str]]:
    assumptions: list[str] = []
    for issue in issues:
        if issue.code == "MISSING_APP_NAME":
            config.app_name = config.app_name or "Untitled App"
            assumptions.append("[repair:root] Set default app_name")
        if issue.code == "MISSING_DESCRIPTION":
            config.description = config.description or "Application generated from requirements"
            assumptions.append("[repair:root] Set default description")
    return config, assumptions


_REPAIR_HANDLERS = {
    "database": _repair_database,
    "api": _repair_api,
    "ui": _repair_ui,
    "auth": _repair_auth,
    "business_logic": _repair_business_logic,
    "root": _repair_root,
}


def repair_config(config: AppConfig, max_iterations: int = 5) -> tuple[AppConfig, ValidationReport]:
    """Repair only broken layers iteratively until valid or max iterations."""
    config = copy.deepcopy(config)
    total_repairs = 0
    repaired_layers: list[str] = []
    clarification_notes: list[str] = []
    clarification_needed = False

    for _ in range(max_iterations):
        report = validate_config(config)
        if report.valid:
            report.repaired_layers = list(dict.fromkeys(repaired_layers))
            report.repair_count = total_repairs
            report.clarification_needed = clarification_needed
            report.clarification_notes = clarification_notes
            config.validation_report = report
            return config, report

        by_layer = _issues_by_layer(report)
        if not by_layer:
            break

        iteration_fixed = False
        for layer, layer_issues in by_layer.items():
            handler = _REPAIR_HANDLERS.get(layer)
            if not handler:
                clarification_needed = True
                clarification_notes.append(f"No repair handler for layer '{layer}'")
                continue

            config, assumptions = handler(config, layer_issues)
            if assumptions:
                config.assumptions.extend(assumptions)
                repaired_layers.append(layer)
                total_repairs += len(assumptions)
                iteration_fixed = True

            unfixable = [i for i in layer_issues if i.code in ("UNKNOWN_ENTITY",) and not assumptions]
            for i in unfixable:
                clarification_needed = True
                clarification_notes.append(i.message)

        if not iteration_fixed:
            break

    final_report = validate_config(config)
    final_report.repaired_layers = list(dict.fromkeys(repaired_layers))
    final_report.repair_count = total_repairs
    final_report.clarification_needed = clarification_needed or not final_report.valid
    final_report.clarification_notes = clarification_notes
    config.validation_report = final_report
    return config, final_report
