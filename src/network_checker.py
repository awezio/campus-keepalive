#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Checker Module
网络状态检测模块

功能:
- 检测当前网络是否在线
- 检测是否被校园网网关踢出（重定向到登录页）
- 获取网关登录页 URL
"""

import socket
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List
import time

try:
    import requests
except ImportError:
    raise ImportError("请安装 requests: pip install requests")

from logger_setup import get_network_logger


class NetworkStatus(Enum):
    """网络状态枚举"""
    ONLINE = "online"           # 正常联网
    OFFLINE = "offline"         # 被网关踢出，需要重新登录
    DISCONNECTED = "disconnected"  # 网络完全断开（WiFi 断开等）
    ERROR = "error"             # 检测异常


@dataclass
class CheckResult:
    """网络检测结果"""
    status: NetworkStatus
    response_code: int
    response_time_ms: float
    redirect_url: Optional[str] = None
    message: str = ""


class NetworkChecker:
    """网络状态检测器"""
    
    # 检测目标 URL（使用 HTTP，因为 HTTPS 无法被网关重定向）
    DEFAULT_CHECK_URLS = [
        ("http://www.baidu.com", "baidu"),
        ("http://connect.rom.miui.com/generate_204", "miui_204"),
        ("http://www.qq.com", "qq"),
        ("http://www.taobao.com", "taobao"),
    ]
    
    # 登录页关键词（用于检测是否被重定向到网关登录页）
    LOGIN_KEYWORDS = [
        'login', 'portal', 'auth', 'eportal', 'webauth',
        '认证', '登录', '登陆', '校园网',
        '10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.',
        '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
        '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
    ]
    
    def __init__(
        self,
        check_urls: Optional[List[Tuple[str, str]]] = None,
        timeout: int = 10,
        login_keywords: Optional[List[str]] = None
    ):
        """
        初始化网络检测器
        
        Args:
            check_urls: 检测用的 URL 列表，格式 [(url, name), ...]
            timeout: 请求超时时间（秒）
            login_keywords: 自定义登录页关键词
        """
        self.check_urls = check_urls or self.DEFAULT_CHECK_URLS
        self.timeout = timeout
        self.login_keywords = login_keywords or self.LOGIN_KEYWORDS
        self.logger = get_network_logger()
        
        # 复用 Session 以提高效率
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _is_login_redirect(self, url: str) -> bool:
        """检查 URL 是否是登录页重定向"""
        if not url:
            return False
        url_lower = url.lower()
        return any(kw in url_lower for kw in self.login_keywords)
    
    def _check_single_url(self, url: str, name: str) -> CheckResult:
        """
        检测单个 URL 的网络状态
        
        Args:
            url: 要检测的 URL
            name: URL 的标识名
        
        Returns:
            CheckResult 检测结果
        """
        start_time = time.time()
        
        try:
            # 使用 HEAD 请求，减少流量消耗
            response = self.session.head(
                url,
                timeout=self.timeout,
                allow_redirects=False
            )
            
            response_time = (time.time() - start_time) * 1000
            status_code = response.status_code
            
            # 检测重定向
            if status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location', '')
                
                if self._is_login_redirect(redirect_url):
                    return CheckResult(
                        status=NetworkStatus.OFFLINE,
                        response_code=status_code,
                        response_time_ms=response_time,
                        redirect_url=redirect_url,
                        message=f"[{name}] Redirected to login portal"
                    )
                else:
                    # 正常重定向（如 HTTP -> HTTPS）
                    return CheckResult(
                        status=NetworkStatus.ONLINE,
                        response_code=status_code,
                        response_time_ms=response_time,
                        redirect_url=redirect_url,
                        message=f"[{name}] Normal redirect"
                    )
            
            elif status_code == 200:
                return CheckResult(
                    status=NetworkStatus.ONLINE,
                    response_code=status_code,
                    response_time_ms=response_time,
                    message=f"[{name}] OK"
                )
            
            elif status_code == 204:
                # generate_204 端点的正常响应
                return CheckResult(
                    status=NetworkStatus.ONLINE,
                    response_code=status_code,
                    response_time_ms=response_time,
                    message=f"[{name}] No Content (expected)"
                )
            
            else:
                return CheckResult(
                    status=NetworkStatus.ERROR,
                    response_code=status_code,
                    response_time_ms=response_time,
                    message=f"[{name}] Unexpected status: {status_code}"
                )
        
        except requests.exceptions.Timeout:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.ERROR,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Timeout"
            )
        
        except requests.exceptions.ConnectionError:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.DISCONNECTED,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Connection failed"
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                status=NetworkStatus.ERROR,
                response_code=0,
                response_time_ms=response_time,
                message=f"[{name}] Error: {str(e)[:50]}"
            )
    
    def check(self) -> CheckResult:
        """
        检测当前网络状态
        
        依次尝试多个 URL，返回第一个确定的结果
        
        Returns:
            CheckResult 检测结果
        """
        last_result = None
        
        for url, name in self.check_urls:
            result = self._check_single_url(url, name)
            last_result = result
            
            # 如果检测到在线或离线（确定性结果），直接返回
            if result.status in (NetworkStatus.ONLINE, NetworkStatus.OFFLINE):
                self.logger.debug(f"Network check: {result.status.value} - {result.message}")
                return result
            
            # 如果是网络断开，继续尝试（可能只是单个服务器问题）
            # 如果是错误，也继续尝试
        
        # 所有 URL 都失败
        if last_result:
            last_result.message = f"All URLs failed. Last: {last_result.message}"
            self.logger.warning(f"Network check failed: {last_result.message}")
            return last_result
        
        return CheckResult(
            status=NetworkStatus.ERROR,
            response_code=0,
            response_time_ms=0,
            message="No URLs to check"
        )
    
    def is_online(self) -> bool:
        """快速检测是否在线"""
        result = self.check()
        return result.status == NetworkStatus.ONLINE
    
    def is_offline(self) -> bool:
        """检测是否被网关踢出（需要重新登录）"""
        result = self.check()
        return result.status == NetworkStatus.OFFLINE
    
    def get_gateway_url(self) -> Optional[str]:
        """
        获取网关登录页 URL
        
        Returns:
            登录页 URL，如果在线则返回 None
        """
        result = self.check()
        if result.status == NetworkStatus.OFFLINE:
            return result.redirect_url
        return None
    
    def check_dns(self, hostname: str = "www.baidu.com") -> bool:
        """
        检测 DNS 解析是否正常
        
        Args:
            hostname: 要解析的域名
        
        Returns:
            DNS 解析是否成功
        """
        try:
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror:
            return False


# 全局实例
_checker: Optional[NetworkChecker] = None


def get_checker() -> NetworkChecker:
    """获取全局 NetworkChecker 实例"""
    global _checker
    if _checker is None:
        _checker = NetworkChecker()
    return _checker


if __name__ == '__main__':
    # 测试
    checker = NetworkChecker()
    
    print("正在检测网络状态...\n")
    
    result = checker.check()
    
    print(f"状态: {result.status.value}")
    print(f"响应码: {result.response_code}")
    print(f"响应时间: {result.response_time_ms:.1f}ms")
    print(f"重定向URL: {result.redirect_url or 'N/A'}")
    print(f"信息: {result.message}")
    
    print(f"\n是否在线: {checker.is_online()}")
    print(f"DNS解析: {'正常' if checker.check_dns() else '异常'}")
