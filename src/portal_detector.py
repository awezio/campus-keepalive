#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portal Detector Module
校园网登录页自动检测模块

功能：
- 检测网络是否需要登录
- 自动捕获校园网登录页 URL
- 识别登录页特征
"""

import re
import requests
from typing import Optional, Tuple
from urllib.parse import urlparse
from logger_setup import get_main_logger


class PortalDetector:
    """校园网登录页检测器"""

    # 已知的校园网登录页 URL 模式
    LOGIN_URL_PATTERNS = [
        r"10\.\d+\.\d+\.\d+",  # 10.x.x.x 私网
        r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",  # 172.16-31.x.x
        r"192\.168\.\d+\.\d+",  # 192.168.x.x
        r"portal\.",  # portal.xxx.com
        r"auth\.",  # auth.xxx.com
        r"eportal\.",  # eportal.xxx.com
        r"login\.",  # login.xxx.com
    ]

    # 登录页关键词
    LOGIN_KEYWORDS = [
        "portal",
        "portal",
        "eportal",
        "login",
        "登录",
        "认证",
        "auth",
        "authentication",
        "captive",
        "login",
        "authenticate",
    ]

    def __init__(self):
        self.logger = get_main_logger()

        # 测试 URL 列表
        self.test_urls = [
            "http://www.baidu.com",
            "http://www.qq.com",
            "http://connect.rom.miui.com/generate_204",
            "http://www.baidu.com",
        ]

    def detect_portal(self) -> Tuple[bool, Optional[str]]:
        """
        检测当前网络是否需要登录，并尝试获取登录页 URL

        Returns:
            Tuple of (needs_login, login_url)
            - needs_login: 是否需要登录
            - login_url: 检测到的登录页 URL，如果无法确定则为 None
        """
        self.logger.info("开始检测校园网登录页...")

        for test_url in self.test_urls:
            try:
                result = self._check_url(test_url)
                if result:
                    needs_login, login_url = result
                    if needs_login:
                        self.logger.info(f"检测到需要登录，登录页 URL: {login_url}")
                        return True, login_url

            except Exception as e:
                self.logger.warning(f"检测 {test_url} 时出错: {e}")
                continue

        # 所有测试都通过，说明不需要登录
        self.logger.info("网络正常，不需要登录")
        return False, None

    def _check_url(self, url: str) -> Optional[Tuple[bool, Optional[str]]]:
        """
        检查单个 URL 是否被重定向到登录页

        Args:
            url: 要测试的 URL

        Returns:
            Tuple of (needs_login, login_url) 或 None
        """
        try:
            # 使用 GET 请求（而不是 HEAD），并限制内容大小
            # HEAD 请求可能被缓存，GET 请求更可靠
            response = requests.get(
                url,
                timeout=5,
                allow_redirects=False,  # 不自动跟随重定向
                stream=True,  # 流式传输，只读取部分内容
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            
            # 只读取前 1KB 内容，避免下载整个页面
            response_content = b''
            if response.status_code == 200:
                try:
                    response_content = response.raw.read(1024)
                except Exception:
                    pass
            
            # 检查是否被重定向
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get("Location", "")
                
                if self._is_login_page(redirect_url):
                    return True, redirect_url
            
            # 检查返回状态 - 200 也可能是登录页
            elif response.status_code == 200:
                # 检查响应内容是否包含登录页特征
                if response_content:
                    content_str = response_content.decode('utf-8', errors='ignore').lower()
                    
                    # 检查是否包含明显的登录表单特征
                    login_page_indicators = [
                        'type="password"',  # 密码输入框
                        'name="password"',
                        'value="登录"',
                        'name="login"',
                        'type="submit"',
                        'username',
                        'password',
                    ]
                    
                    # 如果包含登录表单特征，说明需要登录
                    has_login_form = any(indicator in content_str for indicator in login_page_indicators)
                    
                    if has_login_form:
                        self.logger.debug(f"页面内容包含登录表单特征: {url}")
                        return True, url
                
                # 成功访问，且没有登录表单，不需要登录
                return False, None
            
            # 检查是否 204 No Content（miui_204 特性）
            elif response.status_code == 204:
                return False, None
        except Exception as e:
            self.logger.warning(f"Error in _check_url for {url}: {e}")
            return False, None
    def _is_login_page(self, url: str) -> bool:
        """
        判断 URL 是否是校园网登录页

        Args:
            url: 要检查的 URL

        Returns:
            True 如果是登录页，False 否则
        """
        try:
            parsed = urlparse(url)
            host = parsed.host.lower()
            path = parsed.path.lower()

            # 检查是否匹配已知的登录页 URL 模式
            for pattern in self.LOGIN_URL_PATTERNS:
                if re.search(pattern, host) or re.search(pattern, path):
                    self.logger.debug(f"匹配到登录页模式: {pattern}")
                    return True

            # 检查是否包含登录关键词
            for keyword in self.LOGIN_KEYWORDS:
                if keyword.lower() in host or keyword.lower() in path:
                    self.logger.debug(f"包含登录关键词: {keyword}")
                    return True

            return False

        except Exception as e:
            self.logger.warning(f"判断登录页时出错: {e}")
            return False

    def detect_login_form_fields(self, login_url: str) -> dict:
        """
        检测登录页面的表单字段

        Args:
            login_url: 登录页 URL

        Returns:
            包含表单字段的字典
        """
        try:
            response = requests.get(login_url, timeout=5)
            html = response.text

            # 常见的用户名字段名
            username_fields = [
                "username",
                "user",
                "account",
                "userid",
                "userId",
                "loginName",
                "user_id",
            ]
            # 常见的密码字段名
            password_fields = ["password", "pass", "pwd", "loginPassword"]
            # 常见的提交按钮名
            submit_fields = ["submit", "login", "登录", "loginBtn"]

            detected = {
                "username_field": None,
                "password_field": None,
                "submit_field": None,
                "form_action": None,
            }

            # 简单检测表单字段名
            for field in username_fields:
                if f'name="{field}"' in html or f"name='{field}'" in html:
                    detected["username_field"] = field
                    break

            for field in password_fields:
                if f'name="{field}"' in html or f"name='{field}'" in html:
                    detected["password_field"] = field
                    break

            for field in submit_fields:
                if f'value="{field}"' in html or f"value='{field}'" in html:
                    detected["submit_field"] = field
                    break

            # 检测表单 action
            import re

            action_match = re.search(r'action=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if action_match:
                detected["form_action"] = action_match.group(1)

            self.logger.info(f"检测到的表单字段: {detected}")
            return detected

        except Exception as e:
            self.logger.error(f"检测表单字段时出错: {e}")
            return {}

    def suggest_login_url(self) -> Optional[str]:
        """
        建议可能的登录页 URL

        Returns:
            建议的登录页 URL，如果无法确定则为 None
        """
        needs_login, login_url = self.detect_portal()
        return login_url


if __name__ == "__main__":
    # 测试
    detector = PortalDetector()

    print("检测校园网登录页...")
    needs_login, login_url = detector.detect_portal()

    if needs_login:
        print(f"\n✓ 检测到需要登录")
        print(f"  登录页 URL: {login_url}")

        # 检测表单字段
        fields = detector.detect_login_form_fields(login_url)
        print(f"\n检测到的表单字段:")
        for key, value in fields.items():
            print(f"  {key}: {value}")
    else:
        print("\n✓ 网络正常，不需要登录")
