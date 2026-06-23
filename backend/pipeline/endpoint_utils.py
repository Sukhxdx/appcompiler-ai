"""Helpers for method-aware API endpoint keys."""

from __future__ import annotations

from schemas.app_config import AppConfig


def endpoint_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def all_endpoint_keys(config: AppConfig) -> set[str]:
    return {endpoint_key(ep.method, ep.path) for ep in config.api.endpoints}


def endpoints_for_role(endpoints: list[dict], roles: list[str]) -> list[str]:
    """Build deduplicated method+path keys for endpoints allowed to given roles."""
    seen: set[str] = set()
    keys: list[str] = []
    for ep in endpoints:
        if any(r in ep.get("allowed_roles", []) for r in roles):
            key = endpoint_key(ep["method"], ep["path"])
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def endpoints_for_role_from_config(config: AppConfig, roles: list[str]) -> list[str]:
    seen: set[str] = set()
    keys: list[str] = []
    for ep in config.api.endpoints:
        if any(r in ep.allowed_roles for r in roles):
            key = endpoint_key(ep.method, ep.path)
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def sync_auth_endpoints(config: AppConfig) -> None:
    """Normalize role endpoint permissions to deduplicated METHOD /path keys."""
    for rp in config.auth.roles:
        rp.endpoints = endpoints_for_role_from_config(config, [rp.role])
