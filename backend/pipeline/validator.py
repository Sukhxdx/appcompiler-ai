"""Stage 4: Cross-layer Validation."""

from __future__ import annotations

import re

from schemas.app_config import AppConfig, ValidationIssue, ValidationReport
from pipeline.endpoint_utils import all_endpoint_keys

_COMPUTED_RESPONSE_FIELDS = frozenset({
    "token", "message", "error", "success", "status_code",
    "total_tasks", "completed_tasks", "pending_tasks", "active_users",
    "total_contacts", "new_leads", "revenue", "conversion_rate",
    "active_subscriptions", "total_orders", "total_records", "growth_rate",
})
_SENSITIVE_UI_FIELDS = frozenset({"password", "email"})
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_FORM_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _db_field_names(config: AppConfig) -> dict[str, set[str]]:
    return {t.name: {f.name for f in t.fields} for t in config.database.tables}


def _table_names(config: AppConfig) -> set[str]:
    return {t.name for t in config.database.tables}


def _page_routes(config: AppConfig) -> set[str]:
    return {p.route for p in config.ui.pages}


def _endpoint_by_path(config: AppConfig) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for ep in config.api.endpoints:
        grouped.setdefault(ep.path, []).append(ep)
    return grouped


def _role_names(config: AppConfig) -> set[str]:
    return {r.role for r in config.auth.roles}


def _prompt_hints(config: AppConfig) -> dict:
    text = f"{config.description} {' '.join(config.assumptions)}".lower()
    pages_text = " ".join(p.name.lower() for p in config.ui.pages)
    return {
        "admin_manages_users": (
            "[intent] admin_manages_users=true" in text
            or any(w in text or w in pages_text for w in ("manage user", "user management", "admin user"))
        ),
        "has_payments": "[intent] has_payments=true" in text or any(w in text for w in ("payment", "subscription", "billing", "premium")),
        "has_analytics": any(w in text for w in ("analytics", "dashboard", "metric")),
        "task_assignment": (
            "[intent] task_assignment=true" in text
            or bool(re.search(r"\bassigned tasks\b|\bassign tasks\b", text))
            or "assign" in text
        ),
    }


def validate_config(config: AppConfig) -> ValidationReport:
    issues: list[ValidationIssue] = []
    db_fields = _db_field_names(config)
    tables = _table_names(config)
    pages = _page_routes(config)
    ep_map = _endpoint_by_path(config)
    roles = _role_names(config)
    hints = _prompt_hints(config)

    if not config.app_name:
        issues.append(ValidationIssue(layer="root", severity="error", code="MISSING_APP_NAME", message="app_name is required"))
    if not config.description:
        issues.append(ValidationIssue(layer="root", severity="error", code="MISSING_DESCRIPTION", message="description is required"))

    # API ↔ DB validation
    for ep in config.api.endpoints:
        if not ep.path:
            issues.append(ValidationIssue(layer="api", severity="error", code="MISSING_PATH", message="Endpoint missing path", entity=ep.id))
        if ep.table and ep.table not in tables:
            issues.append(
                ValidationIssue(layer="api", severity="error", code="UNKNOWN_TABLE", message=f"Endpoint references unknown table '{ep.table}'", entity=ep.id, field="table")
            )
        if ep.table and ep.table in db_fields:
            for field in ep.request_fields:
                if field not in db_fields[ep.table]:
                    issues.append(
                        ValidationIssue(layer="api", severity="error", code="UNKNOWN_DB_FIELD", message=f"Request field '{field}' not in table '{ep.table}'", entity=ep.id, field=field)
                    )
            for field in ep.response_fields:
                if field in _COMPUTED_RESPONSE_FIELDS:
                    continue
                if field not in db_fields[ep.table]:
                    issues.append(
                        ValidationIssue(layer="api", severity="warning", code="UNKNOWN_DB_FIELD", message=f"Response field '{field}' not in table '{ep.table}'", entity=ep.id, field=field)
                    )
        for role in ep.allowed_roles:
            if role not in roles:
                issues.append(
                    ValidationIssue(layer="api", severity="error", code="UNKNOWN_ROLE", message=f"Endpoint references unknown role '{role}'", entity=ep.id, field=role)
                )

    # UI ↔ API validation
    for page in config.ui.pages:
        for role in page.allowed_roles:
            if role not in roles:
                issues.append(
                    ValidationIssue(layer="ui", severity="error", code="UNKNOWN_ROLE", message=f"Page '{page.name}' references unknown role '{role}'", entity=page.id, field=role)
                )

        is_dashboard = "dashboard" in page.route.lower() or page.name.lower() == "dashboard"
        is_admin_page = "/admin" in page.route or "user management" in page.name.lower()

        if is_admin_page and "admin" not in page.allowed_roles:
            issues.append(
                ValidationIssue(layer="ui", severity="error", code="ADMIN_PAGE_WRONG_ROLE", message=f"Admin page '{page.name}' must allow admin role only", entity=page.id)
            )

        for comp in page.components:
            data_ep = comp.props.get("data_endpoint")
            method_hint = comp.props.get("method", "POST")

            if comp.type == "form":
                if not comp.submit_endpoint:
                    issues.append(
                        ValidationIssue(layer="ui", severity="error", code="FORM_NO_ENDPOINT", message=f"Form '{comp.id}' missing submit_endpoint", entity=comp.id)
                    )
                elif comp.submit_endpoint not in ep_map:
                    issues.append(
                        ValidationIssue(layer="ui", severity="error", code="UNKNOWN_ENDPOINT", message=f"Form '{comp.id}' submit_endpoint '{comp.submit_endpoint}' not found", entity=comp.id, field="submit_endpoint")
                    )
                else:
                    matching = [e for e in ep_map[comp.submit_endpoint] if e.method in _FORM_METHODS]
                    if not matching:
                        issues.append(
                            ValidationIssue(layer="ui", severity="error", code="FORM_WRONG_METHOD", message=f"Form '{comp.id}' must map to POST/PUT endpoint", entity=comp.id, field=comp.submit_endpoint)
                        )
                    for field in comp.fields:
                        mapped = any(field in e.request_fields for e in matching)
                        if not mapped and matching:
                            issues.append(
                                ValidationIssue(layer="ui", severity="warning", code="FORM_FIELD_UNMAPPED", message=f"Form field '{field}' not in endpoint request_fields", entity=comp.id, field=field)
                            )

            if comp.type == "table":
                endpoint = data_ep or comp.submit_endpoint
                if not endpoint:
                    issues.append(
                        ValidationIssue(layer="ui", severity="error", code="TABLE_NO_GET_ENDPOINT", message=f"Table '{comp.id}' has no data_endpoint", entity=comp.id)
                    )
                elif endpoint not in ep_map:
                    issues.append(
                        ValidationIssue(layer="ui", severity="error", code="UNKNOWN_ENDPOINT", message=f"Table '{comp.id}' data_endpoint '{endpoint}' not found", entity=comp.id, field=endpoint)
                    )
                else:
                    get_eps = [e for e in ep_map[endpoint] if e.method == "GET"]
                    if not get_eps:
                        issues.append(
                            ValidationIssue(layer="ui", severity="error", code="TABLE_NO_GET_ENDPOINT", message=f"Table '{comp.id}' requires GET endpoint at '{endpoint}'", entity=comp.id, field=endpoint)
                        )

            if comp.type in ("card", "chart") and is_dashboard:
                bad = [f for f in comp.fields if f in _SENSITIVE_UI_FIELDS]
                if bad:
                    issues.append(
                        ValidationIssue(layer="ui", severity="error", code="DASHBOARD_LOGIN_FIELDS", message=f"Dashboard component '{comp.id}' must not use login fields: {bad}", entity=comp.id, field=",".join(bad))
                    )
                if not comp.fields and comp.type == "card":
                    issues.append(
                        ValidationIssue(layer="ui", severity="warning", code="DASHBOARD_NO_METRICS", message=f"Dashboard card '{comp.id}' has no metric fields", entity=comp.id)
                    )

    # Semantic requirements
    if hints["admin_manages_users"]:
        has_users_page = any("/users" in p.route or "user management" in p.name.lower() for p in config.ui.pages)
        has_users_get = any(e.path == "/api/users" and e.method == "GET" for e in config.api.endpoints)
        if not has_users_page:
            issues.append(
                ValidationIssue(layer="ui", severity="error", code="MISSING_ADMIN_USERS_PAGE", message="Prompt requires user management but no /admin/users page exists", entity="users_admin")
            )
        if not has_users_get:
            issues.append(
                ValidationIssue(layer="api", severity="error", code="MISSING_USERS_LIST_API", message="User management requires GET /api/users", entity="users_api")
            )

    if hints["has_payments"]:
        if "subscriptions" not in tables and "payments" not in tables:
            issues.append(
                ValidationIssue(layer="database", severity="error", code="MISSING_PAYMENTS_INFRA", message="Payments/premium requires subscriptions or payments table", entity="payments")
            )

    # assignee_id FK validation
    tasks_table = next((t for t in config.database.tables if t.name == "tasks"), None)
    if tasks_table and any(f.name == "assignee_id" for f in tasks_table.fields):
        if "users" not in tables:
            issues.append(
                ValidationIssue(layer="database", severity="error", code="MISSING_USERS_FOR_ASSIGNEE", message="assignee_id requires users table", entity="tasks")
            )
        has_assignee_relation = any(
            r.from_table == "tasks" and r.to_table == "users" and "assignee" in r.name.lower()
            for r in tasks_table.relations
        )
        if not has_assignee_relation:
            issues.append(
                ValidationIssue(
                    layer="database",
                    severity="error",
                    code="MISSING_ASSIGNEE_RELATION",
                    message="assignee_id must have relation tasks.assignee_id -> users.id",
                    entity="tasks",
                    field="assignee_id",
                )
            )
        has_assignee_rule = any(r.name == "valid_task_assignee" for r in config.business_logic.rules)
        if not has_assignee_rule:
            issues.append(
                ValidationIssue(
                    layer="business_logic",
                    severity="error",
                    code="MISSING_ASSIGNEE_RULE",
                    message="assignee_id must be validated by a business rule referencing users",
                    entity="tasks",
                    field="assignee_id",
                )
            )

    if hints["task_assignment"] and tasks_table and not any(f.name == "assignee_id" for f in tasks_table.fields):
        issues.append(
            ValidationIssue(
                layer="database",
                severity="error",
                code="MISSING_ASSIGNEE_FIELD",
                message="Prompt requires task assignment but tasks table lacks assignee_id",
                entity="tasks",
                field="assignee_id",
            )
        )

    # Auth ↔ pages/endpoints (method-aware)
    valid_endpoint_keys = all_endpoint_keys(config)
    for rp in config.auth.roles:
        for page_ref in rp.pages:
            if page_ref not in pages:
                issues.append(
                    ValidationIssue(layer="auth", severity="error", code="UNKNOWN_PAGE", message=f"Role '{rp.role}' references unknown page '{page_ref}'", entity=rp.role, field=page_ref)
                )
        for ep_ref in rp.endpoints:
            if ep_ref not in valid_endpoint_keys:
                issues.append(
                    ValidationIssue(
                        layer="auth",
                        severity="error",
                        code="UNKNOWN_ENDPOINT",
                        message=f"Role '{rp.role}' references unknown endpoint '{ep_ref}' (expected METHOD /path)",
                        entity=rp.role,
                        field=ep_ref,
                    )
                )

    # Business logic
    for rule in config.business_logic.rules:
        for role in rule.applies_to_roles:
            if role not in roles:
                issues.append(
                    ValidationIssue(layer="business_logic", severity="error", code="UNKNOWN_ROLE", message=f"Rule '{rule.name}' references unknown role '{role}'", entity=rule.id, field=role)
                )
        for entity in rule.applies_to_entities:
            if entity not in tables and entity not in {p.id for p in config.ui.pages}:
                issues.append(
                    ValidationIssue(layer="business_logic", severity="error", code="UNKNOWN_ENTITY", message=f"Rule '{rule.name}' references unknown entity '{entity}'", entity=rule.id, field=entity)
                )

    if config.auth.enabled and not config.auth.roles:
        issues.append(ValidationIssue(layer="auth", severity="error", code="NO_ROLES", message="Auth enabled but no roles defined"))

    errors = [i for i in issues if i.severity == "error"]
    return ValidationReport(valid=len(errors) == 0, issues=issues)
