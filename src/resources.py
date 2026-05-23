#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resource path helpers for source and PyInstaller builds."""

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the immutable resource root for source or bundled execution."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def executable_dir() -> Path:
    """Return the writable directory next to the executable or repo root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Return a path under the bundled resource root."""
    return app_root().joinpath(*parts)
