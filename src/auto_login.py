#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Login Module
自动登录模块

功能:
- 自动登录校园网 Web Portal
- 支持多种常见的校园网认证系统
- 抓取登录页面并解析表单字段
"""

import re
import time
from typing import Dict, Optional, Tuple, List
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    raise ImportError("请安装 requests: pip install requests")

from logger_setup import get_login_logger
from network_checker import NetworkChecker, NetworkStatus


@dataclass
class LoginResult:
    """登录结果"""
    success: bool
    message: str
    redirect_url: Optional[str] = None
    response_code: int = 0


class AutoLogin:
    """自动登录器"""
    
    # 常见的登录成功标志
    SUCCESS_KEYWORDS = [
        'success', '成功', '登录成功', 'online', '认证成功', '已连接',
        'logged in', 'welcome', '欢迎'
    ]
    
    # 常见的登录失败标志
    FAILURE_KEYWORDS = [
        'error', 'failed', '失败', '错误', '密码错误', '账号不存在',
        'invalid', '认证失败', '用户名或密码'
    ]
    
    def __init__(
        self,
        login_url: str,
        username: str,
        password: str,
        extra_fields: Optional[Dict[str, str]] = None,
        timeout: int = 15
    ):
        """
        初始化自动登录器
        
        Args:
            login_url: 登录页面 URL
            username: 用户名
            password: 密码
            extra_fields: 额外的表单字段
            timeout: 请求超时时间
        """
        self.login_url = login_url
        self.username = username
        self.password = password
        self.extra_fields = extra_fields or {}
        self.timeout = timeout
        
        self.logger = get_login_logger()
        self.checker = NetworkChecker()
        
        # HTTP Session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        # 缓存的表单信息
        self._form_action: Optional[str] = None
        self._form_fields: Dict[str, str] = {}
        self._username_field: str = 'username'
        self._password_field: str = 'password'
    
    def _parse_login_page(self, html: str, base_url: str) -> Tuple[Optional[str], Dict[str, str], str, str]:
        """
        解析登录页面，提取表单信息
        
        Args:
            html: 页面 HTML 内容
            base_url: 页面的 URL（用于解析相对路径）
        
        Returns:
            Tuple of (form_action, hidden_fields, username_field_name, password_field_name)
        """
        hidden_fields = {}
        form_action = None
        username_field = 'username'
        password_field = 'password'
        
        # 查找表单 action
        form_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if form_match:
            action = form_match.group(1)
            if action:
                form_action = urljoin(base_url, action)
        
        # 查找隐藏字段
        hidden_pattern = r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']*)["\'][^>]*value=["\']([^"\']*)["\']'
        for match in re.finditer(hidden_pattern, html, re.IGNORECASE):
            hidden_fields[match.group(1)] = match.group(2)
        
        # 反向查找（value 在 name 前面）
        hidden_pattern2 = r'<input[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']*)["\'][^>]*type=["\']hidden["\']'
        for match in re.finditer(hidden_pattern2, html, re.IGNORECASE):
            hidden_fields[match.group(2)] = match.group(1)
        
        # 查找用户名字段名
        username_patterns = [
            r'<input[^>]*name=["\']([^"\']*user[^"\']*)["\'][^>]*type=["\']text["\']',
            r'<input[^>]*type=["\']text["\'][^>]*name=["\']([^"\']*user[^"\']*)["\']',
            r'<input[^>]*name=["\']([^"\']*account[^"\']*)["\']',
            r'<input[^>]*name=["\']([^"\']*login[^"\']*)["\']',
        ]
        for pattern in username_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                username_field = match.group(1)
                break
        
        # 查找密码字段名
        password_patterns = [
            r'<input[^>]*name=["\']([^"\']*pass[^"\']*)["\'][^>]*type=["\']password["\']',
            r'<input[^>]*type=["\']password["\'][^>]*name=["\']([^"\']*)["\']',
        ]
        for pattern in password_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                password_field = match.group(1)
                break
        
        return form_action, hidden_fields, username_field, password_field
    def _log_cookie_status(self, context: str):
        """
        记录当前Session的Cookie状态
        
        Args:
            context: 调用上下文描述
        """
        cookies = list(self.session.cookies)
        if cookies:
            self.logger.debug(f"Cookies ({context}): {len(cookies)} cookies - {[c.name for c in cookies]}")
        else:
            self.logger.debug(f"Cookies ({context}): No cookies set")
    
    def _warm_up_session(self) -> bool:
        """
        预热会话，发送轻量GET请求到根路径
        
        Returns:
            bool: 是否成功预热
        """
        parsed = urlparse(self.login_url)
        root_url = f"{parsed.scheme}://{parsed.netloc}/"
        
        self.logger.info(f"Warming up session: GET {root_url}")
        
        try:
            response = self.session.get(root_url, timeout=self.timeout)
            self.logger.debug(f"Warm-up response: status={response.status_code}, url={response.url}")
            self._log_cookie_status("after warm-up")
            return True
        except Exception as e:
            self.logger.warning(f"Warm-up request failed: {e}")
            return False
    
    def analyze_login_page(self, retry_count: int = 2) -> Dict:
        """
        分析登录页面，返回表单结构信息
        
        Args:
            retry_count: 失败时的重试次数
        
        Returns:
            包含表单分析结果的字典
        """
        self.logger.info(f"Analyzing login page: {self.login_url}")
        
        for attempt in range(retry_count + 1):
            try:
                response = self.session.get(self.login_url, timeout=self.timeout)
                response.raise_for_status()
                
                html = response.text
                form_action, hidden_fields, username_field, password_field = self._parse_login_page(
                    html, self.login_url
                )
                
                # 缓存表单信息
                self._form_action = form_action or self.login_url
                self._form_fields = hidden_fields
                self._username_field = username_field
                self._password_field = password_field
                
                self._log_cookie_status("after analyze")
                
                result = {
                    'url': self.login_url,
                    'form_action': self._form_action,
                    'username_field': username_field,
                    'password_field': password_field,
                    'hidden_fields': hidden_fields,
                    'html_length': len(html)
                }
                
                self.logger.info(f"Form analysis: action={self._form_action}, "
                               f"username={username_field}, password={password_field}, "
                               f"hidden_fields={len(hidden_fields)}")
                
                return result
                
            except RequestException as e:
                if attempt < retry_count:
                    self.logger.warning(f"Analyze attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(1)
                else:
                    self.logger.error(f"Failed to analyze login page after {retry_count + 1} attempts: {e}")
                    return {'error': str(e)}
            except Exception as e:
                self.logger.error(f"Failed to analyze login page: {e}")
                return {'error': str(e)}

    def login(self) -> LoginResult:
        """
        执行登录操作
        
        Returns:
            LoginResult 登录结果
        """
        self.logger.info(f"Attempting login: {self.login_url}")
        
        # 1. 预热会话 - 在分析页面前先访问根路径
        self._warm_up_session()
        
        # 2. 分析登录页面（如果还没分析过）
        if not self._form_action:
            analysis_result = self.analyze_login_page()
            if 'error' in analysis_result:
                return LoginResult(
                    success=False,
                    message=f"Failed to analyze login page: {analysis_result['error']}",
                    response_code=0
                )
        
        # 3. 构建登录表单数据
        form_data = dict(self._form_fields)  # 从隐藏字段开始
        form_data[self._username_field] = self.username
        form_data[self._password_field] = self.password
        form_data.update(self.extra_fields)  # 添加额外字段
        
        post_url = self._form_action or self.login_url
        
        self.logger.debug(f"POST to {post_url}, fields: {list(form_data.keys())}")
        self._log_cookie_status("before POST")
        
        try:
            # 4. 发送登录POST请求，添加Referer头
            response = self.session.post(
                post_url,
                data=form_data,
                headers={'Referer': self.login_url},
                timeout=self.timeout,
                allow_redirects=True
            )
            
            self.logger.debug(f"POST response: status={response.status_code}, url={response.url}")
            self._log_cookie_status("after POST")
            
            html = response.text.lower()
            
            # 5. 改进登录结果判定 - 多因素检查
            
            # 检查1: 响应状态码
            status_code = response.status_code
            if status_code == 200:
                self.logger.debug(f"Status code: 200 OK")
            elif status_code in (301, 302, 303, 307, 308):
                self.logger.debug(f"Status code: {status_code} Redirect to {response.url}")
            else:
                self.logger.warning(f"Status code: {status_code}")
            
            # 检查2: URL变化 (重定向后URL是否改变)
            url_changed = response.url != self.login_url
            if url_changed:
                self.logger.info(f"URL changed from {self.login_url} to {response.url}")
            
            # 检查3: 响应内容中的成功关键词
            success_indicators = []
            for keyword in self.SUCCESS_KEYWORDS:
                if keyword in html:
                    success_indicators.append(f"keyword:'{keyword}'")
                    self.logger.debug(f"Found success keyword: {keyword}")
            
            # 检查4: 响应内容中的失败关键词
            failure_indicators = []
            for keyword in self.FAILURE_KEYWORDS:
                if keyword in html:
                    failure_indicators.append(f"keyword:'{keyword}'")
                    self.logger.debug(f"Found failure keyword: {keyword}")
            
            # 5. 综合判定登录结果
            if success_indicators and not failure_indicators:
                # 有成功指标且无失败指标 -> 判定为成功
                self.logger.info(f"Login successful (indicators: {success_indicators})")
                return LoginResult(
                    success=True,
                    message="Login successful",
                    redirect_url=response.url,
                    response_code=response.status_code
                )
            elif failure_indicators:
                # 有失败指标 -> 判定为失败
                self.logger.warning(f"Login failed (indicators: {failure_indicators})")
                return LoginResult(
                    success=False,
                    message=f"Login failed: {failure_indicators[0]}",
                    response_code=response.status_code
                )
            elif status_code in (301, 302, 303, 307, 308) and url_changed:
                # 只有重定向和URL变化 -> 可能成功，等待验证
                self.logger.info("Login appears successful (redirect + URL change)")
                time.sleep(1)  # 等待认证生效
                if self.checker.is_online():
                    self.logger.info("Login successful (verified by network check)")
                    return LoginResult(
                        success=True,
                        message="Login successful (network verified)",
                        redirect_url=response.url,
                        response_code=response.status_code
                    )
            
            # 6. 最后手段：通过网络检测验证
            time.sleep(1)  # 等待认证生效
            if self.checker.is_online():
                self.logger.info("Login successful (verified by network check)")
                return LoginResult(
                    success=True,
                    message="Login successful (network verified)",
                    response_code=response.status_code
                )
            
            # 7. 无法确定
            self.logger.warning("Login status uncertain - no clear indicators")
            return LoginResult(
                success=False,
                message="Login status uncertain",
                response_code=response.status_code
            )
            
        except RequestException as e:
            self.logger.error(f"Login request failed: {e}")
            return LoginResult(
                success=False,
                message=f"Request failed: {str(e)}"
            )
    
    def login_with_retry(self, max_retries: int = 3, delay: int = 5) -> LoginResult:
        """
        带重试的登录
        
        Args:
            max_retries: 最大重试次数
            delay: 重试间隔（秒）
        
        Returns:
            LoginResult 登录结果
        """
        last_result = None
        
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"Login attempt {attempt}/{max_retries}")
            
            result = self.login()
            last_result = result
            
            if result.success:
                return result
            
            if attempt < max_retries:
                self.logger.info(f"Waiting {delay}s before retry...")
                time.sleep(delay)
        
        return last_result or LoginResult(
            success=False,
            message="All login attempts failed"
        )
    
    def verify_connection(self) -> bool:
        """验证当前网络连接状态"""
        return self.checker.is_online()


class CaptureHelper:
    """登录抓包辅助工具"""
    
    @staticmethod
    def print_browser_instructions(login_url: str):
        """打印浏览器抓包指南"""
        instructions = f"""
================================================================================
校园网登录抓包指南
================================================================================

步骤：
1. 打开浏览器，按 F12 打开开发者工具
2. 切换到 "Network" (网络) 标签页
3. 勾选 "Preserve log" (保留日志)
4. 访问登录页面: {login_url}
5. 填写账号密码，点击登录
6. 在 Network 面板中找到登录请求（通常是 POST 请求）
7. 右键该请求 -> "Copy" -> "Copy as cURL (bash)"
8. 将复制的内容粘贴到这里

需要记录的信息：
- POST URL（登录请求发送的地址）
- 表单字段名（username/password 对应的字段名可能不同）
- 其他必要的隐藏字段

常见的用户名字段名：
- username, userName, user, userid, user_id, account, loginName

常见的密码字段名：
- password, passwd, pass, pwd, userPwd

================================================================================
"""
        print(instructions)
    
    @staticmethod
    def parse_curl_command(curl_command: str) -> Dict:
        """
        解析 cURL 命令，提取 POST 数据
        
        Args:
            curl_command: 从浏览器复制的 cURL 命令
        
        Returns:
            包含 url, method, headers, data 的字典
        """
        result = {
            'url': '',
            'method': 'GET',
            'headers': {},
            'data': {}
        }
        
        # 提取 URL
        url_match = re.search(r"curl\s+'([^']+)'", curl_command)
        if url_match:
            result['url'] = url_match.group(1)
        
        # 检测方法
        if '-X POST' in curl_command or '--data' in curl_command or '-d ' in curl_command:
            result['method'] = 'POST'
        
        # 提取 headers
        header_pattern = r"-H\s+'([^:]+):\s*([^']+)'"
        for match in re.finditer(header_pattern, curl_command):
            result['headers'][match.group(1)] = match.group(2)
        
        # 提取 POST data
        data_pattern = r"(?:--data(?:-raw)?|-d)\s+'([^']+)'"
        data_match = re.search(data_pattern, curl_command)
        if data_match:
            data_str = data_match.group(1)
            # 解析 URL 编码的表单数据
            for pair in data_str.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    from urllib.parse import unquote
                    result['data'][unquote(key)] = unquote(value)
        
        return result


if __name__ == '__main__':
    # 测试模式
    print("Auto Login Module Test")
    print("=" * 60)
    
    # 打印抓包指南
    CaptureHelper.print_browser_instructions("http://your-portal-url/")
    
    # 如果有配置，测试登录分析
    try:
        from config_manager import get_config
        config = get_config()
        
        if config.portal.login_url:
            print(f"\nAnalyzing configured login page: {config.portal.login_url}")
            
            login = AutoLogin(
                login_url=config.portal.login_url,
                username=config.portal.username or "test",
                password=config.portal.password or "test",
                extra_fields=config.portal.extra_fields
            )
            
            result = login.analyze_login_page()
            print(f"\nAnalysis result:")
            for key, value in result.items():
                print(f"  {key}: {value}")
        else:
            print("\nNo login URL configured. Please edit config.yaml")
            
    except Exception as e:
        print(f"\nError: {e}")
