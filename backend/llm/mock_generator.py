"""Deterministic rich AppConfig generation from prompt profiles."""

from __future__ import annotations

from typing import Any, Optional

from llm.prompt_analyzer import PromptProfile, analyze_prompt
from pipeline.endpoint_utils import endpoints_for_role


def build_intent_dict(profile: PromptProfile) -> dict[str, Any]:
    category = "internal_tool"
    if profile.has_tasks:
        category = "crud"
    if profile.has_products or profile.has_orders:
        category = "ecommerce"

    goal = profile.raw[:200] if len(profile.raw) < 200 else profile.raw[:197] + "..."
    if profile.has_tasks:
        goal = "Build a task management application with role-based access"
    if profile.has_contacts:
        goal = "Build a CRM with contacts, dashboard, and role-based access"

    return {
        "app_name": profile.app_name,
        "category": category,
        "primary_goal": goal,
        "target_users": ["end users", "administrators"],
        "roles": profile.roles,
        "core_features": profile.features,
        "entities": profile.entities,
        "constraints": ["responsive UI", "REST API"],
        "ambiguities": profile.ambiguities,
        "requires_auth": not profile.auth_disabled or profile.auth_conflict,
        "requires_payment": profile.has_payments,
        "raw_prompt": profile.raw,
    }


def build_design_dict(profile: PromptProfile) -> dict[str, Any]:
    tables = _build_tables(profile)
    endpoints = _build_endpoints(profile, tables)
    pages = _build_pages(profile)
    rules = _build_business_rules(profile)

    assumptions = ["Deterministic mock generation — REST API with JWT auth"]
    if profile.auth_conflict:
        assumptions.append("Auth enabled despite 'no login' because admin user management requires authentication")

    return {
        "app_name": profile.app_name,
        "description": f"System design for {profile.app_name}",
        "raw_prompt": profile.raw,
        "pages": pages,
        "endpoints": endpoints,
        "tables": [{"name": t["name"], "fields": t["fields"], "relations": t.get("relations", [])} for t in tables],
        "roles": [
            {"name": "admin", "permissions": ["read", "write", "delete", "manage_users"]},
            {"name": "user", "permissions": ["read", "write"]},
            {"name": "guest", "permissions": ["read"]},
        ],
        "business_rules": rules,
        "assumptions": assumptions,
    }


def build_schema_dict(profile: PromptProfile) -> dict[str, Any]:
    design = build_design_dict(profile)
    endpoints = []
    for i, ep in enumerate(design["endpoints"]):
        endpoints.append({"id": f"ep_{i}", **ep})

    tables = []
    for t in design["tables"]:
        fields = []
        for f in t["fields"]:
            ftype = "uuid" if f in ("id",) or f.endswith("_id") else "integer" if f.endswith("_count") or f in ("amount",) else "string"
            fields.append({"name": f, "type": ftype, "required": f != "id", "unique": f == "id"})
        if t["name"] == "tasks":
            relations = _task_db_relations(profile)
        else:
            relations = []
            for rel in t.get("relations", []):
                relations.append(
                    {"name": f"{t['name']}_to_{rel}", "from_table": t["name"], "to_table": rel, "type": "many_to_one"}
                )
        tables.append({"name": t["name"], "fields": fields, "relations": relations})

    pages = _build_ui_pages(profile, endpoints)

    admin_pages = [p["route"] for p in pages if "admin" in p["allowed_roles"]]
    user_pages = [p["route"] for p in pages if "user" in p["allowed_roles"]]
    guest_pages = [p["route"] for p in pages if "guest" in p["allowed_roles"]]

    admin_eps = endpoints_for_role(endpoints, ["admin"])
    user_eps = endpoints_for_role(endpoints, ["user"])
    guest_eps = endpoints_for_role(endpoints, ["guest"])

    return {
        "app_name": profile.app_name,
        "description": design["description"],
        "assumptions": design["assumptions"],
        "ui": {"pages": pages},
        "api": {"endpoints": endpoints},
        "database": {"tables": tables},
        "auth": {
            "enabled": not profile.auth_disabled or profile.auth_conflict,
            "roles": [
                {"role": "admin", "permissions": ["read", "write", "delete", "manage_users"], "pages": admin_pages, "endpoints": admin_eps},
                {"role": "user", "permissions": ["read", "write"], "pages": user_pages, "endpoints": user_eps},
                {"role": "guest", "permissions": ["read"], "pages": guest_pages, "endpoints": guest_eps},
            ],
        },
        "business_logic": {
            "rules": [
                {
                    "id": r.get("id", f"rule_{r['name']}"),
                    "name": r["name"],
                    "description": r["description"],
                    "condition": r.get("condition", ""),
                    "applies_to_roles": r["applies_to_roles"],
                    "applies_to_entities": r["applies_to_entities"],
                }
                for r in design["business_rules"]
            ]
        },
        "execution_plan": {
            "steps": [
                {"order": 1, "action": "scaffold", "target": "database", "details": "Create tables, relations, and migrations"},
                {"order": 2, "action": "implement", "target": "api", "details": "Build REST endpoints with RBAC"},
                {"order": 3, "action": "build", "target": "ui", "details": "Create pages, forms, tables, and dashboard cards"},
                {"order": 4, "action": "configure", "target": "auth", "details": "Wire role permissions to pages and endpoints"},
                {"order": 5, "action": "simulate", "target": "runtime", "details": "Validate executable deployment plan"},
            ],
            "estimated_complexity": "high" if profile.has_payments else "medium",
        },
    }


def _build_tables(profile: PromptProfile) -> list[dict[str, Any]]:
    tables = [
        {"name": "users", "fields": ["id", "email", "password", "role", "created_at"], "relations": []},
    ]
    if profile.has_tasks:
        task_fields = _task_table_fields(profile)
        tables.append({"name": "tasks", "fields": task_fields, "relations": ["users"]})
    if profile.has_contacts:
        tables.append({"name": "contacts", "fields": ["id", "name", "email", "phone", "company", "owner_id"], "relations": ["users"]})
    if profile.has_products:
        tables.append({"name": "products", "fields": ["id", "name", "sku", "price", "stock_count"], "relations": []})
    if profile.has_orders:
        tables.append({"name": "orders", "fields": ["id", "user_id", "total_amount", "status"], "relations": ["users"]})
    if profile.has_blog:
        tables.append({"name": "posts", "fields": ["id", "title", "body", "author_id"], "relations": ["users"]})
    if profile.has_payments:
        tables.append(
            {
                "name": "subscriptions",
                "fields": ["id", "user_id", "plan", "status", "amount", "stripe_id"],
                "relations": ["users"],
            }
        )
        tables.append(
            {"name": "payments", "fields": ["id", "user_id", "amount", "status", "subscription_id"], "relations": ["users", "subscriptions"]}
        )
    return tables


def _build_endpoints(profile: PromptProfile, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_names = {t["name"] for t in tables}
    eps: list[dict[str, Any]] = []

    if not profile.auth_disabled or profile.auth_conflict:
        eps.append(
            {
                "path": "/api/auth/login",
                "method": "POST",
                "description": "Authenticate user",
                "request_fields": ["email", "password"],
                "response_fields": ["id", "email", "role"],
                "table": "users",
                "allowed_roles": ["guest"],
            }
        )

    eps.append(
        {
            "path": "/api/analytics/summary",
            "method": "GET",
            "description": "Dashboard analytics summary",
            "request_fields": [],
            "response_fields": _dashboard_metrics(profile),
            "table": None,
            "allowed_roles": ["admin", "user"],
        }
    )

    if profile.has_tasks:
        task_req = _task_request_fields(profile)
        task_res = _task_response_fields(profile)
        eps.extend(
            [
                {
                    "path": "/api/tasks",
                    "method": "GET",
                    "description": "List tasks",
                    "request_fields": [],
                    "response_fields": task_res,
                    "table": "tasks",
                    "allowed_roles": ["user", "admin"],
                },
                {
                    "path": "/api/tasks",
                    "method": "POST",
                    "description": "Create task",
                    "request_fields": task_req,
                    "response_fields": task_res,
                    "table": "tasks",
                    "allowed_roles": ["user", "admin"],
                },
                {
                    "path": "/api/tasks/{id}",
                    "method": "PUT",
                    "description": "Update task",
                    "request_fields": task_req,
                    "response_fields": task_res,
                    "table": "tasks",
                    "allowed_roles": ["user", "admin"],
                },
            ]
        )

    if profile.has_contacts:
        eps.extend(
            [
                {
                    "path": "/api/contacts",
                    "method": "GET",
                    "description": "List contacts",
                    "request_fields": [],
                    "response_fields": ["id", "name", "email", "phone", "company"],
                    "table": "contacts",
                    "allowed_roles": ["user", "admin"],
                },
                {
                    "path": "/api/contacts",
                    "method": "POST",
                    "description": "Create contact",
                    "request_fields": ["name", "email", "phone", "company"],
                    "response_fields": ["id", "name", "email"],
                    "table": "contacts",
                    "allowed_roles": ["user", "admin"],
                },
            ]
        )

    if profile.has_products and "products" in table_names:
        eps.append(
            {
                "path": "/api/products",
                "method": "GET",
                "description": "List products",
                "request_fields": [],
                "response_fields": ["id", "name", "sku", "price", "stock_count"],
                "table": "products",
                "allowed_roles": ["admin", "user"],
            }
        )

    if profile.has_orders and "orders" in table_names:
        eps.append(
            {
                "path": "/api/orders",
                "method": "GET",
                "description": "List orders",
                "request_fields": [],
                "response_fields": ["id", "user_id", "total_amount", "status"],
                "table": "orders",
                "allowed_roles": ["admin", "user"],
            }
        )

    if profile.admin_manages_users or profile.auth_conflict:
        eps.extend(
            [
                {
                    "path": "/api/users",
                    "method": "GET",
                    "description": "List users (admin)",
                    "request_fields": [],
                    "response_fields": ["id", "email", "role"],
                    "table": "users",
                    "allowed_roles": ["admin"],
                },
                {
                    "path": "/api/users/{id}",
                    "method": "PUT",
                    "description": "Update user (admin)",
                    "request_fields": ["email", "role"],
                    "response_fields": ["id", "email", "role"],
                    "table": "users",
                    "allowed_roles": ["admin"],
                },
                {
                    "path": "/api/users/{id}",
                    "method": "DELETE",
                    "description": "Delete user (admin)",
                    "request_fields": [],
                    "response_fields": ["id"],
                    "table": "users",
                    "allowed_roles": ["admin"],
                },
            ]
        )

    if profile.has_payments:
        eps.extend(
            [
                {
                    "path": "/api/subscriptions",
                    "method": "GET",
                    "description": "List subscriptions",
                    "request_fields": [],
                    "response_fields": ["id", "user_id", "plan", "status", "amount"],
                    "table": "subscriptions",
                    "allowed_roles": ["admin", "user"],
                },
                {
                    "path": "/api/payments",
                    "method": "POST",
                    "description": "Process payment",
                    "request_fields": ["user_id", "amount", "subscription_id"],
                    "response_fields": ["id", "status", "amount"],
                    "table": "payments",
                    "allowed_roles": ["user", "admin"],
                },
            ]
        )

    return eps


def _dashboard_metrics(profile: PromptProfile) -> list[str]:
    metrics = ["active_users"]
    if profile.has_tasks:
        metrics.extend(["total_tasks", "completed_tasks", "pending_tasks"])
    if profile.has_contacts:
        metrics.extend(["total_contacts", "new_leads"])
    if profile.has_payments:
        metrics.extend(["revenue", "conversion_rate", "active_subscriptions"])
    if profile.has_orders:
        metrics.append("total_orders")
    if not profile.has_tasks and not profile.has_contacts:
        metrics.extend(["total_records", "growth_rate"])
    return metrics


def _build_pages(profile: PromptProfile) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []

    if not profile.auth_disabled or profile.auth_conflict:
        pages.append(
            {
                "name": "Login",
                "route": "/login",
                "description": "Authentication",
                "components": ["login_form"],
                "allowed_roles": ["guest"],
            }
        )

    pages.append(
        {
            "name": "Dashboard",
            "route": "/dashboard",
            "description": "Analytics dashboard",
            "components": ["dashboard_metrics"],
            "allowed_roles": ["admin", "user"],
        }
    )

    if profile.has_tasks:
        comps = ["task_form", "task_edit_form", "tasks_table"]
        pages.append(
            {
                "name": "Tasks",
                "route": "/tasks",
                "description": "Task management",
                "components": comps,
                "allowed_roles": ["user", "admin"],
            }
        )

    if profile.has_contacts:
        pages.append(
            {
                "name": "Contacts",
                "route": "/contacts",
                "description": "CRM contacts",
                "components": ["contact_form", "contacts_table"],
                "allowed_roles": ["user", "admin"],
            }
        )

    if profile.admin_manages_users or profile.auth_conflict:
        pages.append(
            {
                "name": "User Management",
                "route": "/admin/users",
                "description": "Admin user management",
                "components": ["users_table", "user_edit_form"],
                "allowed_roles": ["admin"],
            }
        )

    if profile.has_payments:
        pages.append(
            {
                "name": "Billing",
                "route": "/billing",
                "description": "Subscriptions and payments",
                "components": ["subscription_table", "payment_form"],
                "allowed_roles": ["user", "admin"],
            }
        )

    if profile.has_analytics:
        pages.append(
            {
                "name": "Analytics",
                "route": "/admin/analytics",
                "description": "Admin analytics",
                "components": ["analytics_chart", "analytics_metrics"],
                "allowed_roles": ["admin"],
            }
        )

    return pages


def _build_ui_pages(profile: PromptProfile, endpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ep_by_path = {e["path"]: e for e in endpoints}
    pages = []

    for p in _build_pages(profile):
        components = []
        for comp_name in p["components"]:
            comp = _component_from_name(comp_name, p["route"], profile, ep_by_path)
            components.append(comp)
        pages.append(
            {
                "id": p["route"].strip("/").replace("/", "_") or "home",
                "name": p["name"],
                "route": p["route"],
                "components": components,
                "allowed_roles": p["allowed_roles"],
            }
        )
    return pages


def _component_from_name(name: str, route: str, profile: PromptProfile, ep_by_path: dict) -> dict[str, Any]:
    base_id = f"{route.strip('/').replace('/', '_')}_{name}"

    if name == "login_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Login",
            "fields": ["email", "password"],
            "submit_endpoint": "/api/auth/login",
            "props": {},
        }

    if name == "dashboard_metrics":
        return {
            "id": base_id,
            "type": "card",
            "label": "Dashboard Metrics",
            "fields": _dashboard_metrics(profile),
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/analytics/summary"},
        }

    if name == "task_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Create Task",
            "fields": _task_request_fields(profile),
            "submit_endpoint": "/api/tasks",
            "props": {"method": "POST"},
        }

    if name == "task_edit_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Update Task",
            "fields": _task_request_fields(profile),
            "submit_endpoint": "/api/tasks/{id}",
            "props": {"method": "PUT"},
        }

    if name == "tasks_table":
        return {
            "id": base_id,
            "type": "table",
            "label": "Tasks",
            "fields": _task_response_fields(profile),
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/tasks"},
        }

    if name == "contact_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Add Contact",
            "fields": ["name", "email", "phone", "company"],
            "submit_endpoint": "/api/contacts",
            "props": {"method": "POST"},
        }

    if name == "contacts_table":
        return {
            "id": base_id,
            "type": "table",
            "label": "Contacts",
            "fields": ["id", "name", "email", "phone", "company"],
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/contacts"},
        }

    if name == "users_table":
        return {
            "id": base_id,
            "type": "table",
            "label": "Users",
            "fields": ["id", "email", "role"],
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/users"},
        }

    if name == "user_edit_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Edit User",
            "fields": ["email", "role"],
            "submit_endpoint": "/api/users/{id}",
            "props": {"method": "PUT"},
        }

    if name == "subscription_table":
        return {
            "id": base_id,
            "type": "table",
            "label": "Subscriptions",
            "fields": ["id", "plan", "status", "amount"],
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/subscriptions"},
        }

    if name == "payment_form":
        return {
            "id": base_id,
            "type": "form",
            "label": "Process Payment",
            "fields": ["user_id", "amount", "subscription_id"],
            "submit_endpoint": "/api/payments",
            "props": {"method": "POST"},
        }

    if name in ("analytics_chart", "analytics_metrics"):
        return {
            "id": base_id,
            "type": "chart",
            "label": "Analytics",
            "fields": _dashboard_metrics(profile),
            "submit_endpoint": None,
            "props": {"data_endpoint": "/api/analytics/summary"},
        }

    return {
        "id": base_id,
        "type": "card",
        "label": name.replace("_", " ").title(),
        "fields": [],
        "submit_endpoint": None,
        "props": {},
    }


def _build_business_rules(profile: PromptProfile) -> list[dict[str, Any]]:
    rules = [
        {
            "name": "auth_required",
            "description": "Protected routes require authenticated admin or user role",
            "condition": "user.role in ['admin','user']",
            "applies_to_roles": ["user", "admin"],
            "applies_to_entities": ["users"],
        }
    ]
    if profile.has_task_assignment:
        rules.append(
            {
                "id": "rule_valid_assignee",
                "name": "valid_task_assignee",
                "description": "Task assignee must reference an existing user.",
                "condition": "assignee_id exists in users.id",
                "applies_to_roles": ["user", "admin"],
                "applies_to_entities": ["tasks", "users"],
            }
        )
    if profile.admin_manages_users:
        rules.append(
            {
                "name": "admin_only_user_mgmt",
                "description": "Only admins can list, edit, or delete users",
                "condition": "user.role == 'admin'",
                "applies_to_roles": ["admin"],
                "applies_to_entities": ["users"],
            }
        )
    if profile.has_payments:
        rules.append(
            {
                "name": "premium_billing",
                "description": "Premium features require active subscription",
                "condition": "subscription.status == 'active'",
                "applies_to_roles": ["user"],
                "applies_to_entities": ["subscriptions", "payments"],
            }
        )
    if profile.auth_conflict:
        rules.append(
            {
                "name": "auth_conflict_resolution",
                "description": "Auth enabled despite no-login request because admin management requires identity",
                "condition": "clarification_needed",
                "applies_to_roles": ["admin"],
                "applies_to_entities": ["users"],
            }
        )
    return rules


def _task_table_fields(profile: PromptProfile) -> list[str]:
    fields = ["id", "title", "status", "user_id", "created_at"]
    if profile.has_task_assignment:
        fields.append("assignee_id")
    if profile.intentional_priority_gap:
        # Omit priority from DB initially — triggers repair when UI/API reference it.
        pass
    elif "priority" in profile.lower and profile.has_tasks:
        fields.append("priority")
    return fields


def _task_request_fields(profile: PromptProfile) -> list[str]:
    fields = ["title", "status"]
    if profile.has_task_assignment:
        fields.append("assignee_id")
    if profile.intentional_priority_gap or ("priority" in profile.lower and profile.has_tasks):
        fields.append("priority")
    return fields


def _task_response_fields(profile: PromptProfile) -> list[str]:
    fields = ["id", "title", "status", "user_id"]
    if profile.has_task_assignment:
        fields.append("assignee_id")
    if profile.intentional_priority_gap or ("priority" in profile.lower and profile.has_tasks):
        fields.append("priority")
    return fields


def _task_db_relations(profile: PromptProfile) -> list[dict[str, str]]:
    relations = [{"name": "task_owner", "from_table": "tasks", "to_table": "users", "type": "many_to_one"}]
    if profile.has_task_assignment:
        relations.append({"name": "task_assignee", "from_table": "tasks", "to_table": "users", "type": "many_to_one"})
    return relations


def generate_from_prompt(prompt: str, app_name: Optional[str] = None) -> tuple[dict, dict, dict]:
    """Return (intent, design, schema) dicts for a prompt."""
    profile = analyze_prompt(prompt, app_name)
    return build_intent_dict(profile), build_design_dict(profile), build_schema_dict(profile)
