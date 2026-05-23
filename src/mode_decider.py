#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime mode decision helpers."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuntimeMode(str, Enum):
    """Supported Windows runtime modes."""

    AUTO = "auto"
    KEEPALIVE_ONLY = "keepalive_only"
    AUTO_LOGIN = "auto_login"


@dataclass(frozen=True)
class NetworkSnapshot:
    """Small, dependency-free view of current network status."""

    status: str
    redirect_url: Optional[str] = None


def normalize_mode(value: object) -> RuntimeMode:
    """Normalize persisted or user-entered mode values."""
    try:
        return RuntimeMode(str(value or RuntimeMode.AUTO.value))
    except ValueError:
        return RuntimeMode.AUTO


def has_portal_credentials(config: object) -> bool:
    """Return True when login URL, username, and password are present."""
    portal = getattr(config, "portal", None)
    if portal is None:
        return False

    return all(
        str(getattr(portal, field, "") or "").strip()
        for field in ("login_url", "username", "password")
    )


def is_auto_login_enabled(config: object) -> bool:
    """Return True when auto-login is enabled in configuration."""
    auto_login = getattr(config, "auto_login", None)
    return bool(getattr(auto_login, "enabled", True))


def network_needs_login(snapshot: NetworkSnapshot) -> bool:
    """Return True when external internet access is not currently available."""
    status = str(snapshot.status or "").lower()
    if bool(snapshot.redirect_url):
        return True

    if status in {"", "unknown", "checking", "online"}:
        return False

    return True


def can_start_login_flow(config: object) -> bool:
    """Return True when the app is allowed to open a login flow."""
    return is_auto_login_enabled(config)


def decide_runtime_mode(config: object, snapshot: NetworkSnapshot) -> RuntimeMode:
    """Decide whether to keep alive only or perform auto-login."""
    app = getattr(config, "app", None)
    configured = normalize_mode(getattr(app, "mode", RuntimeMode.AUTO.value))

    if configured == RuntimeMode.KEEPALIVE_ONLY:
        return RuntimeMode.KEEPALIVE_ONLY

    if configured == RuntimeMode.AUTO_LOGIN:
        if can_start_login_flow(config):
            return RuntimeMode.AUTO_LOGIN
        return RuntimeMode.KEEPALIVE_ONLY

    if (
        network_needs_login(snapshot)
        and can_start_login_flow(config)
    ):
        return RuntimeMode.AUTO_LOGIN

    return RuntimeMode.KEEPALIVE_ONLY
