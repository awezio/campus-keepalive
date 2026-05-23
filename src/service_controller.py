#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-UI service orchestration for the PySide front-end."""

import threading
import time
import webbrowser
import os
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Callable, Optional

from config_manager import DEFAULT_LOGIN_URL
from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode


@dataclass
class RuntimeStatus:
    """UI-facing status snapshot."""

    mode: RuntimeMode = RuntimeMode.KEEPALIVE_ONLY
    network_status: str = "unknown"
    heartbeat_running: bool = False
    reconnecting: bool = False
    checking: bool = False
    paused: bool = False
    last_check: Optional[datetime] = None
    last_error: str = ""
    total_beats: int = 0
    successful_beats: int = 0
    failed_beats: int = 0


@dataclass
class ReconnectGate(AbstractContextManager):
    """Small lock that always resets reconnecting state."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    active: bool = False

    def __enter__(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("reconnection already in progress")
        self.active = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.active = False
        self._lock.release()
        return False


class ServiceController:
    """Coordinates network checks, heartbeat, and auto-login without owning UI widgets."""

    def __init__(
        self,
        config,
        on_status: Optional[Callable[[RuntimeStatus], None]] = None,
        browser_open: Optional[Callable[[str], object]] = None,
    ):
        self.config = config
        self.on_status = on_status
        self._browser_open = browser_open or webbrowser.open
        self.status = RuntimeStatus()
        self._gate = ReconnectGate()
        self._heartbeat = None
        self._checker = None
        self._auto_login = None
        self._threads = []
        self._closed = False
        self._status_lock = threading.Lock()
        self._last_browser_open_at = 0.0
        self._browser_open_interval_seconds = 90

    def _emit(self):
        if self.on_status:
            self.on_status(replace(self.status))

    def _run_async(self, target: Callable[[], None]):
        thread = threading.Thread(target=target, daemon=True)
        self._threads.append(thread)
        thread.start()
        return thread

    def update_config(self, config):
        self.config = config
        self._auto_login = None
        if self._heartbeat:
            self._heartbeat.set_interval(config.keepalive.interval_seconds)

    def start(self):
        self._ensure_heartbeat()
        if self._heartbeat:
            self._heartbeat.start(run_immediately=False)
            self.status.heartbeat_running = True
            self._emit()
        self.check_now()

    def stop(self):
        self._closed = True
        if self._heartbeat:
            self._heartbeat.stop()
            self.status.heartbeat_running = False
        self._emit()

    def pause(self):
        if self._heartbeat:
            self._heartbeat.pause()
        self.status.paused = True
        self.status.heartbeat_running = False
        self._emit()

    def resume(self):
        if self._heartbeat:
            self._heartbeat.resume()
        self.status.paused = False
        self.status.heartbeat_running = True
        self._emit()

    def check_now(self):
        with self._status_lock:
            self.status.checking = True
            self.status.network_status = "checking"
            self.status.last_error = ""
        self._emit()

        def worker():
            try:
                checker = self._ensure_checker()
                result = checker.check()
                snapshot = NetworkSnapshot(
                    status=getattr(result.status, "value", str(result.status)),
                    redirect_url=result.redirect_url,
                )
                with self._status_lock:
                    self.status.network_status = snapshot.status
                    self.status.mode = decide_runtime_mode(self.config, snapshot)
                    self.status.last_check = datetime.now()
                    self.status.last_error = "" if snapshot.status != "error" else result.message
                    self.status.checking = False
                self._emit()
                if self.status.mode == RuntimeMode.AUTO_LOGIN:
                    self.reconnect_now()
            except Exception as exc:
                with self._status_lock:
                    self.status.last_error = str(exc)
                    self.status.last_check = datetime.now()
                    self.status.checking = False
                self._emit()

        return self._run_async(worker)

    def reconnect_now(self):
        def worker():
            try:
                with self._gate:
                    self.status.reconnecting = True
                    self.status.last_error = ""
                    self._emit()

                    opened_browser = self._open_login_page()
                    self.status.last_error = (
                        "Browser opened for campus login; complete login manually."
                        if opened_browser
                        else "Browser login page was opened recently; complete login manually."
                    )
            except RuntimeError as exc:
                self.status.last_error = str(exc)
            except Exception as exc:
                self.status.last_error = str(exc)
            finally:
                self.status.reconnecting = False
                self._emit()

        return self._run_async(worker)

    def _on_heartbeat_online(self, result):
        self.status.network_status = "online"
        self.status.mode = decide_runtime_mode(
            self.config, NetworkSnapshot(status="online", redirect_url=None)
        )
        self._copy_heartbeat_stats()
        self._emit()

    def _on_heartbeat_offline(self, result):
        snapshot = NetworkSnapshot(
            status=getattr(result.status, "value", str(result.status)),
            redirect_url=result.redirect_url,
        )
        self.status.network_status = snapshot.status
        self.status.mode = decide_runtime_mode(self.config, snapshot)
        self._copy_heartbeat_stats()
        self._emit()
        if self.status.mode == RuntimeMode.AUTO_LOGIN:
            self.reconnect_now()

    def _on_heartbeat_error(self, result):
        snapshot = NetworkSnapshot(
            status=getattr(result.status, "value", str(result.status)),
            redirect_url=getattr(result, "redirect_url", None),
        )
        self.status.network_status = snapshot.status
        self.status.mode = decide_runtime_mode(self.config, snapshot)
        self.status.last_error = result.message
        self._copy_heartbeat_stats()
        self._emit()
        if self.status.mode == RuntimeMode.AUTO_LOGIN:
            self.reconnect_now()

    def _copy_heartbeat_stats(self):
        if not self._heartbeat:
            return
        stats = self._heartbeat.get_stats()
        self.status.total_beats = stats.total_beats
        self.status.successful_beats = stats.successful_beats
        self.status.failed_beats = stats.failed_beats
        self.status.last_check = datetime.now()

    def _ensure_checker(self):
        if self._checker is None:
            from network_checker import NetworkChecker

            self._checker = NetworkChecker()
        return self._checker

    def _ensure_heartbeat(self):
        if self._heartbeat is None:
            from heartbeat import Heartbeat

            self._heartbeat = Heartbeat(
                interval=self.config.keepalive.interval_seconds,
                targets=self.config.keepalive.targets,
                on_online=self._on_heartbeat_online,
                on_offline=self._on_heartbeat_offline,
                on_error=self._on_heartbeat_error,
            )
        return self._heartbeat

    def _ensure_auto_login(self):
        if self._auto_login is None:
            from auto_login import AutoLogin

            self._auto_login = AutoLogin(
                login_url=self.config.portal.login_url,
                username=self.config.portal.username,
                password=self.config.portal.password,
                extra_fields=self.config.portal.extra_fields,
            )
        return self._auto_login

    def _login_page_url(self) -> str:
        portal = getattr(self.config, "portal", None)
        login_url = str(getattr(portal, "login_url", "") or "").strip()
        if login_url:
            return login_url

        return DEFAULT_LOGIN_URL

    def _open_login_page(self) -> bool:
        now = time.monotonic()
        if now - self._last_browser_open_at < self._browser_open_interval_seconds:
            return False

        url = self._login_page_url()
        opened = False
        try:
            # Prefer the injected opener (used by tests and by UI to control behavior)
            result = self._browser_open(url)
            opened = bool(result) or result is None
        except Exception:
            opened = False

        if not opened and sys.platform == "win32":
            try:
                os.startfile(url)
                opened = True
            except Exception:
                opened = False

        if opened:
            self._last_browser_open_at = now
        return opened
