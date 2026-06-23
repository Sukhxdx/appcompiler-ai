"""Stage 6: Runtime Simulation — verify config is executable."""

from __future__ import annotations

from schemas.app_config import AppConfig, RuntimeSimulationResult


def simulate_runtime(config: AppConfig) -> RuntimeSimulationResult:
    checks: list[dict] = []
    failures: list[str] = []

    ep_by_path: dict[str, list] = {}
    for e in config.api.endpoints:
        ep_by_path.setdefault(e.path, []).append(e)

    table_names = {t.name for t in config.database.tables}
    role_names = {r.role for r in config.auth.roles}

    # Pages renderable
    if not config.ui.pages:
        failures.append("No UI pages defined")
        checks.append({"check": "pages_renderable", "passed": False})
    else:
        renderable = all(p.route and p.name for p in config.ui.pages)
        checks.append({"check": "pages_renderable", "passed": renderable, "count": len(config.ui.pages)})
        if not renderable:
            failures.append("Some pages missing route or name")

    # Forms submit to valid POST/PUT APIs
    form_checks = []
    for page in config.ui.pages:
        for comp in page.components:
            if comp.type == "form":
                ep = comp.submit_endpoint
                valid = ep is not None and ep in ep_by_path and any(e.method in ("POST", "PUT", "PATCH") for e in ep_by_path[ep])
                form_checks.append(valid)
                if not valid:
                    failures.append(f"Form '{comp.id}' on '{page.name}' has no valid POST/PUT submit endpoint")
    checks.append({"check": "forms_submit_to_valid_apis", "passed": all(form_checks) if form_checks else True, "form_count": len(form_checks)})

    # Tables map to GET APIs
    table_checks = []
    for page in config.ui.pages:
        for comp in page.components:
            if comp.type == "table":
                data_ep = comp.props.get("data_endpoint")
                valid = data_ep and data_ep in ep_by_path and any(e.method == "GET" for e in ep_by_path[data_ep])
                table_checks.append(valid)
                if not valid:
                    failures.append(f"Table '{comp.id}' on '{page.name}' has no valid GET data_endpoint")
    checks.append({"check": "tables_map_to_get_apis", "passed": all(table_checks) if table_checks else True, "table_count": len(table_checks)})

    # APIs connect to DB tables
    ep_db_checks = []
    for ep in config.api.endpoints:
        if ep.method in ("POST", "PUT", "PATCH", "DELETE"):
            mapped = ep.table is not None and ep.table in table_names
            ep_db_checks.append(mapped)
            if not mapped:
                failures.append(f"Mutating endpoint '{ep.path}' does not map to a database table")
        elif ep.method == "GET" and ep.table:
            ep_db_checks.append(ep.table in table_names)
    checks.append({"check": "apis_connect_to_database", "passed": all(ep_db_checks) if ep_db_checks else True})

    # Auth enforceable
    rbac_checks = []
    for page in config.ui.pages:
        rbac_checks.append(all(r in role_names for r in page.allowed_roles))
    for ep in config.api.endpoints:
        rbac_checks.append(all(r in role_names for r in ep.allowed_roles))
    rbac_passed = all(rbac_checks) if rbac_checks else not config.auth.enabled
    checks.append({"check": "auth_rules_enforceable", "passed": rbac_passed})
    if not rbac_passed:
        failures.append("Role-based access references undefined roles")

    # Admin users page check when GET /api/users exists
    if any(e.path == "/api/users" and e.method == "GET" for e in config.api.endpoints):
        has_admin_users_page = any("/users" in p.route and "admin" in p.allowed_roles for p in config.ui.pages)
        checks.append({"check": "admin_users_page_present", "passed": has_admin_users_page})
        if not has_admin_users_page:
            failures.append("GET /api/users exists but no admin users page found")

    validation_ok = config.validation_report.valid
    checks.append({"check": "validation_passed", "passed": validation_ok})
    if not validation_ok:
        failures.append("Validation report indicates errors remain")

    executable = len(failures) == 0
    result = RuntimeSimulationResult(executable=executable, checks=checks, failures=failures)
    config.runtime = result
    return result
