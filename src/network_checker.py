#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Network status detection for captive-portal campus networks."""

import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

try:
    import requests
except ImportError:
    raise ImportError("Please install requests: pip install requests")

from logger_setup import get_network_logger


class NetworkStatus(Enum):
    """Network status values returned by NetworkChecker."""

    ONLINE = "online"
    OFFLINE = "offline"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result from a single network check."""

    status: NetworkStatus
    response_code: int
    response_time_ms: float
    redirect_url: Optional[str] = None
    message: str = ""


class NetworkChecker:
    """Detect internet access and captive-portal login redirects."""

    WINDOWS_NCSI_URL = "http://www.msftconnecttest.com/connecttest.txt"
    WINDOWS_NCSI_EXPECTED = "Microsoft Connect Test"

    DEFAULT_CHECK_URLS = [
        (WINDOWS_NCSI_URL, "windows_ncsi"),
        ("http://connect.rom.miui.com/generate_204", "miui_204"),
        ("http://www.baidu.com", "baidu"),
        ("http://www.qq.com", "qq"),
    ]

    LOGIN_KEYWORDS = [
        "login",
        "portal",
        "auth",
        "eportal",
        "webauth",
        "10.",
        "192.168.",
        "172.16.",
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
    ]

    LOGIN_FORM_INDICATORS = [
        'type="password"',
        "name=\"password\"",
        "name='password'",
        "username",
        "password",
        "eportal",
        "webauth",
        "portal",
        "login",
    ]

    def __init__(
        self,
        check_urls: Optional[List[Tuple[str, str]]] = None,
        timeout: int = 3,
        login_keywords: Optional[List[str]] = None,
    ):
        self.check_urls = check_urls or self.DEFAULT_CHECK_URLS
        self.timeout = timeout
        self.login_keywords = login_keywords or self.LOGIN_KEYWORDS
        self.logger = get_network_logger()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

    def _is_login_redirect(self, url: str) -> bool:
        if not url:
            return False
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in self.login_keywords)

    def _read_response_prefix(self, response, size: int = 1024) -> str:
        content = b""
        try:
            raw = getattr(response, "raw", None)
            if raw:
                content = raw.read(size)
            if not content and getattr(response, "content", b""):
                content = response.content[:size]
        except Exception:
            content = b""

        if isinstance(content, str):
            return content[:size].lower()
        return content.decode("utf-8", errors="ignore").lower()

    def _looks_like_login_page(self, content: str) -> bool:
        return any(indicator in content for indicator in self.LOGIN_FORM_INDICATORS)

    def _result_from_response(self, url: str, name: str, response, start_time: float) -> CheckResult:
        response_time = (time.time() - start_time) * 1000
        status_code = response.status_code

        if status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            if self._is_login_redirect(redirect_url):
                return CheckResult(
                    status=NetworkStatus.OFFLINE,
                    response_code=status_code,
                    response_time_ms=response_time,
                    redirect_url=redirect_url,
                    message=f"[{name}] Redirected to login portal",
                )

            return CheckResult(
                status=NetworkStatus.ONLINE,
                response_code=status_code,
                response_time_ms=response_time,
                redirect_url=redirect_url,
                message=f"[{name}] Normal redirect",
            )

        if status_code == 200:
            content = self._read_response_prefix(response)
            if content and self._looks_like_login_page(content):
                return CheckResult(
                    status=NetworkStatus.OFFLINE,
                    response_code=status_code,
                    response_time_ms=response_time,
                    redirect_url=url,
                    message=f"[{name}] Login portal content",
                )

            if (
                url == self.WINDOWS_NCSI_URL
                and content
                and self.WINDOWS_NCSI_EXPECTED.lower() not in content
            ):
                return CheckResult(
                    status=NetworkStatus.OFFLINE,
                    response_code=status_code,
                    response_time_ms=response_time,
                    redirect_url=url,
                    message=f"[{name}] Captive portal response",
                )

            return CheckResult(
                status=NetworkStatus.ONLINE,
                response_code=status_code,
                response_time_ms=response_time,
                message=f"[{name}] OK",
            )

        if status_code == 204:
            return CheckResult(
                status=NetworkStatus.ONLINE,
                response_code=status_code,
                response_time_ms=response_time,
                message=f"[{name}] No Content (expected)",
            )

        return CheckResult(
            status=NetworkStatus.ERROR,
            response_code=status_code,
            response_time_ms=response_time,
            message=f"[{name}] Unexpected status: {status_code}",
        )

    def _request_url(self, method: str, url: str, name: str, start_time: float) -> CheckResult:
        request = self.session.get if method == "GET" else self.session.head

        try:
            kwargs = {"timeout": self.timeout, "allow_redirects": False}
            if method == "GET":
                kwargs["stream"] = True
            response = request(url, **kwargs)
            return self._result_from_response(url, name, response, start_time)

        except requests.exceptions.Timeout:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.ERROR,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Timeout",
            )

        except requests.exceptions.ConnectionError:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.DISCONNECTED,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Connection failed",
            )

        except Exception as exc:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.ERROR,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Error: {str(exc)[:50]}",
            )

    def _check_single_url(self, url: str, name: str) -> CheckResult:
        start_time = time.time()

        if url == self.WINDOWS_NCSI_URL:
            return self._request_url("GET", url, name, start_time)

        # Try a lightweight HEAD first to be fast, but verify with GET when
        # HEAD returns 200/ONLINE because some captive portals respond to GET
        # with a login page while HEAD appears OK and would cause false-positives.
        result = self._request_url("HEAD", url, name, start_time)
        if result.status in (NetworkStatus.ERROR, NetworkStatus.DISCONNECTED):
            return self._request_url("GET", url, name, start_time)

        if result.status == NetworkStatus.ONLINE and result.response_code == 200:
            # Verify content with GET to detect captive-portal pages that only
            # appear on GET requests.
            get_result = self._request_url("GET", url, name, start_time)
            # Prefer the GET result if it indicates offline/portal, otherwise
            # return the GET result to have accurate timings and content checks.
            return get_result

        return result

    def check(self) -> CheckResult:
        last_result = None

        for url, name in self.check_urls:
            result = self._check_single_url(url, name)
            last_result = result

            if result.status in (NetworkStatus.ONLINE, NetworkStatus.OFFLINE):
                self.logger.debug(f"Network check: {result.status.value} - {result.message}")
                return result

        if last_result:
            last_result.message = f"All URLs failed. Last: {last_result.message}"
            self.logger.warning(f"Network check failed: {last_result.message}")
            return last_result

        return CheckResult(
            status=NetworkStatus.ERROR,
            response_code=0,
            response_time_ms=0,
            message="No URLs to check",
        )

    def is_online(self) -> bool:
        return self.check().status == NetworkStatus.ONLINE

    def is_offline(self) -> bool:
        return self.check().status == NetworkStatus.OFFLINE

    def get_gateway_url(self) -> Optional[str]:
        result = self.check()
        if result.status == NetworkStatus.OFFLINE:
            return result.redirect_url
        return None

    def check_dns(self, hostname: str = "www.baidu.com") -> bool:
        try:
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror:
            return False


_checker: Optional[NetworkChecker] = None


def get_checker() -> NetworkChecker:
    global _checker
    if _checker is None:
        _checker = NetworkChecker()
    return _checker


if __name__ == "__main__":
    checker = NetworkChecker()
    result = checker.check()

    print(f"Status: {result.status.value}")
    print(f"Code: {result.response_code}")
    print(f"Time: {result.response_time_ms:.1f}ms")
    print(f"Redirect: {result.redirect_url or 'N/A'}")
    print(f"Message: {result.message}")
    print(f"Online: {checker.is_online()}")
    print(f"DNS: {'OK' if checker.check_dns() else 'FAILED'}")
