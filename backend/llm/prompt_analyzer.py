"""Deterministic prompt analysis for mock generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_POST_RE = re.compile(r"\bposts?\b|\bblog\b|\barticle")
_TASK_RE = re.compile(r"\btasks?\b|\btodo")
_CONTACT_RE = re.compile(r"\bcontacts?\b|\bcrm\b|\bcustomer|\blead")
_PRODUCT_RE = re.compile(r"\bproducts?\b|\binventory\b|\bcatalog\b|\bshop\b")
_ORDER_RE = re.compile(r"\borders?\b")
_PAYMENT_RE = re.compile(r"\bpayments?\b|\bstripe\b|\bbilling\b|\bcheckout\b|\bsubscribe")
_PREMIUM_RE = re.compile(r"\bpremium\b|\bpaid plan\b|\bsubscription")
_ANALYTICS_RE = re.compile(r"\banalytics\b|\bconversion\b|\brevenue\b|\breport")
_ADMIN_USERS_RE = re.compile(r"\bmanage (all )?users\b|\buser management\b|\badmins? (can )?manage")
_AUTH_DISABLED_RE = re.compile(r"\bno login\b|\bno auth\b|\bwithout login\b|\bwithout auth\b")
_ASSIGN_RE = re.compile(r"\bassign(?:ed|ee|ing)?\b")
_TASK_ASSIGN_PHRASE_RE = re.compile(r"\bassigned tasks\b|\bassign tasks\b")
_VAGUE_RE = re.compile(r"\bsomething\b|\bmaybe\b|\bnot sure\b|\bvague\b|\bstuff\b")


@dataclass
class PromptProfile:
    raw: str
    lower: str
    app_name: str
    has_tasks: bool = False
    has_contacts: bool = False
    has_products: bool = False
    has_orders: bool = False
    has_blog: bool = False
    admin_manages_users: bool = False
    has_payments: bool = False
    has_premium: bool = False
    has_analytics: bool = False
    auth_disabled: bool = False
    auth_conflict: bool = False
    vague: bool = False
    has_task_assignment: bool = False
    intentional_priority_gap: bool = False
    entities: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)


def analyze_prompt(prompt: str, app_name: Optional[str] = None) -> PromptProfile:
    lower = prompt.lower()
    name = app_name or _infer_app_name(prompt)

    has_tasks = bool(_TASK_RE.search(lower))
    has_contacts = bool(_CONTACT_RE.search(lower))
    has_products = bool(_PRODUCT_RE.search(lower))
    has_orders = bool(_ORDER_RE.search(lower))
    has_blog = bool(_POST_RE.search(lower))
    admin_manages_users = bool(_ADMIN_USERS_RE.search(lower)) or (
        "admin" in lower and "user" in lower and any(w in lower for w in ("manage", "delete", "edit"))
    )
    has_payments = bool(_PAYMENT_RE.search(lower))
    has_premium = bool(_PREMIUM_RE.search(lower))
    has_analytics = bool(_ANALYTICS_RE.search(lower)) or "dashboard" in lower
    auth_disabled = bool(_AUTH_DISABLED_RE.search(lower))
    auth_conflict = auth_disabled and admin_manages_users
    vague = bool(_VAGUE_RE.search(lower))
    has_task_assignment = has_tasks and ("assign" in lower and "task" in lower)
    intentional_priority_gap = has_tasks and "priority" in lower

    entities = ["users"]
    if has_tasks:
        entities.append("tasks")
    if has_contacts:
        entities.append("contacts")
    if has_products:
        entities.append("products")
    if has_orders:
        entities.append("orders")
    if has_blog:
        entities.append("posts")
    if has_payments or has_premium:
        entities.append("subscriptions")

    roles = ["admin", "user", "guest"]
    if "manager" in lower:
        roles.append("manager")

    features = ["authentication", "dashboard"]
    if has_tasks:
        features.append("task CRUD")
    if has_task_assignment:
        features.append("task assignment")
    if has_contacts:
        features.append("contact management")
    if admin_manages_users:
        features.append("admin user management")
    if has_payments or has_premium:
        features.append("payments and subscriptions")
    if has_analytics:
        features.append("analytics and reporting")

    ambiguities: list[str] = []
    if vague:
        ambiguities.append("Requirements are vague; features inferred from keywords")
    if auth_conflict:
        ambiguities.append("Conflict: no login requested but admins must manage users — auth enabled with clarification flag")

    return PromptProfile(
        raw=prompt,
        lower=lower,
        app_name=name,
        has_tasks=has_tasks,
        has_contacts=has_contacts,
        has_products=has_products,
        has_orders=has_orders,
        has_blog=has_blog,
        admin_manages_users=admin_manages_users,
        has_payments=has_payments or has_premium,
        has_premium=has_premium,
        has_analytics=has_analytics or "dashboard" in lower,
        auth_disabled=auth_disabled,
        auth_conflict=auth_conflict,
        has_task_assignment=has_task_assignment,
        intentional_priority_gap=intentional_priority_gap,
        vague=vague,
        entities=entities,
        roles=roles,
        features=features,
        ambiguities=ambiguities,
    )


def _infer_app_name(prompt: str) -> str:
    lower = prompt.lower()
    if "crm" in lower:
        return "CRM Platform"
    if "task" in lower or "todo" in lower:
        return "Task Management App"
    if "shop" in lower or "ecommerce" in lower:
        return "E-Commerce App"
    if "blog" in lower:
        return "Blog Platform"
    words = [w.strip(".,!?") for w in prompt.split() if len(w) > 3][:3]
    if words:
        return " ".join(w.capitalize() for w in words[:2]) + " App"
    return "Generated App"
