#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config Manager Module
配置管理模块

功能:
- 加载和保存 YAML 配置文件
- 密码加密存储（AES）
- 配置验证
"""

import base64
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    raise ImportError("请安装 PyYAML: pip install pyyaml")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from logger_setup import get_main_logger, get_base_dir


# 配置文件路径（使用与 logger 相同的基础目录）
BASE_DIR = get_base_dir()
CONFIG_FILE = BASE_DIR / "config.yaml"
KEY_FILE = BASE_DIR / ".key"  # 加密密钥文件（自动生成）
DEFAULT_LOGIN_URL = "http://192.168.2.135/eportal/success.jsp?"
LEGACY_DEFAULT_LOGIN_URL = "http://10.0.0.1/eportal/index.jsp"

@dataclass
class PortalConfig:
    """网关配置"""
    login_url: str = DEFAULT_LOGIN_URL
    username: str = ""
    password: str = ""  # 明文或加密后的密码
    password_encrypted: bool = False  # 标记密码是否已加密
    extra_fields: Dict[str, str] = field(default_factory=dict)  # 额外的表单字段


@dataclass
class KeepaliveConfig:
    """保活配置"""
    interval_seconds: int = 120  # 心跳间隔（秒）
    targets: list = field(default_factory=lambda: [
        "http://www.baidu.com",
        "http://connect.rom.miui.com/generate_204"
    ])


@dataclass
class AutoLoginConfig:
    """自动登录配置"""
    enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 5


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    max_size_mb: int = 5
    backup_count: int = 3


@dataclass
class AppSettings:
    """应用级配置"""
    mode: str = "auto"
    start_minimized: bool = False
    show_notifications: bool = True


@dataclass
class AppConfig:
    """完整应用配置"""
    app: AppSettings = field(default_factory=AppSettings)
    portal: PortalConfig = field(default_factory=PortalConfig)
    keepalive: KeepaliveConfig = field(default_factory=KeepaliveConfig)
    auto_login: AutoLoginConfig = field(default_factory=AutoLoginConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录的 config.yaml
        """
        self.config_path = config_path or CONFIG_FILE
        self.key_path = KEY_FILE
        self.logger = get_main_logger()
        self._fernet: Optional[Fernet] = None
        
        # 初始化加密器
        if HAS_CRYPTO:
            self._init_crypto()
    
    def _init_crypto(self):
        """初始化加密器"""
        try:
            if self.key_path.exists():
                # 加载现有密钥
                key = self.key_path.read_bytes()
            else:
                # 生成新密钥
                key = Fernet.generate_key()
                self.key_path.write_bytes(key)
                # 设置文件权限（仅限 Windows 可读）
                if os.name == 'nt':
                    import stat
                    os.chmod(self.key_path, stat.S_IRUSR | stat.S_IWUSR)
            
            self._fernet = Fernet(key)
        except Exception as e:
            self.logger.warning(f"Failed to initialize encryption: {e}")
            self._fernet = None
    
    def encrypt_password(self, password: str) -> str:
        """
        加密密码
        
        Args:
            password: 明文密码
        
        Returns:
            Base64 编码的加密密码
        """
        if not self._fernet:
            self.logger.warning("Encryption not available, storing password as-is")
            return password
        
        encrypted = self._fernet.encrypt(password.encode('utf-8'))
        return base64.b64encode(encrypted).decode('ascii')
    
    def decrypt_password(self, encrypted: str) -> str:
        """
        解密密码
        
        Args:
            encrypted: Base64 编码的加密密码
        
        Returns:
            明文密码
        """
        if not self._fernet:
            return encrypted
        
        try:
            encrypted_bytes = base64.b64decode(encrypted.encode('ascii'))
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            self.logger.error(f"Failed to decrypt password: {e}")
            return encrypted
    
    def load(self) -> AppConfig:
        """
        加载配置文件
        
        Returns:
            AppConfig 实例
        """
        config = AppConfig()
        
        if not self.config_path.exists():
            self.logger.info(f"Config file not found, using defaults: {self.config_path}")
            return config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # 解析 app 配置（旧配置没有该段，使用默认值）
            if 'app' in data:
                app = data['app']
                config.app = AppSettings(
                    mode=app.get('mode', 'auto'),
                    start_minimized=app.get('start_minimized', False),
                    show_notifications=app.get('show_notifications', True)
                )
            
            # 解析 portal 配置
            if 'portal' in data:
                portal = data['portal']
                config.portal = PortalConfig(
                    login_url=(
                        DEFAULT_LOGIN_URL
                        if (portal.get('login_url') or '').strip() in ('', LEGACY_DEFAULT_LOGIN_URL)
                        else portal.get('login_url')
                    ),
                    username=portal.get('username', ''),
                    password=portal.get('password', ''),
                    password_encrypted=portal.get('password_encrypted', False),
                    extra_fields=portal.get('extra_fields', {})
                )
                
                # 如果密码已加密，解密它
                if config.portal.password_encrypted and config.portal.password:
                    config.portal.password = self.decrypt_password(config.portal.password)
            
            # 解析 keepalive 配置
            if 'keepalive' in data:
                ka = data['keepalive']
                config.keepalive = KeepaliveConfig(
                    interval_seconds=ka.get('interval_seconds', 120),
                    targets=ka.get('targets', config.keepalive.targets)
                )
            
            # 解析 auto_login 配置
            if 'auto_login' in data:
                al = data['auto_login']
                config.auto_login = AutoLoginConfig(
                    enabled=al.get('enabled', True),
                    max_retries=al.get('max_retries', 3),
                    retry_delay_seconds=al.get('retry_delay_seconds', 5)
                )
            
            # 解析 logging 配置
            if 'logging' in data:
                lg = data['logging']
                config.logging = LoggingConfig(
                    level=lg.get('level', 'INFO'),
                    max_size_mb=lg.get('max_size_mb', 5),
                    backup_count=lg.get('backup_count', 3)
                )
            
            self.logger.info(f"Config loaded from {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
        
        return config
    
    def save(self, config: AppConfig, encrypt_password: bool = True):
        """
        保存配置文件
        
        Args:
            config: AppConfig 实例
            encrypt_password: 是否加密密码
        """
        # 准备密码（加密或明文）
        password = config.portal.password
        password_encrypted = False
        
        if encrypt_password and password and self._fernet:
            password = self.encrypt_password(password)
            password_encrypted = True
        
        data = {
            'app': {
                'mode': config.app.mode,
                'start_minimized': config.app.start_minimized,
                'show_notifications': config.app.show_notifications
            },
            'portal': {
                'login_url': config.portal.login_url,
                'username': config.portal.username,
                'password': password,
                'password_encrypted': password_encrypted,
                'extra_fields': config.portal.extra_fields
            },
            'keepalive': {
                'interval_seconds': config.keepalive.interval_seconds,
                'targets': config.keepalive.targets
            },
            'auto_login': {
                'enabled': config.auto_login.enabled,
                'max_retries': config.auto_login.max_retries,
                'retry_delay_seconds': config.auto_login.retry_delay_seconds
            },
            'logging': {
                'level': config.logging.level,
                'max_size_mb': config.logging.max_size_mb,
                'backup_count': config.logging.backup_count
            }
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Config saved to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise
    
    def create_example(self):
        """创建示例配置文件"""
        example_path = self.config_path.parent / "config.example.yaml"
        
        example_content = """# Campus Network Keep-Alive 配置文件
# 请复制此文件为 config.yaml 并填写你的信息

app:
  # 运行模式: auto=自动判断, keepalive_only=仅保活, auto_login=强制自动登录
  mode: "auto"

  # 启动后是否最小化到托盘
  start_minimized: false

  # 是否显示系统通知
  show_notifications: true

portal:
  # 校园网登录页 URL（必填）
  # 通常形如 http://10.x.x.x/eportal/ 或 http://portal.xxx.edu.cn/
  login_url: "http://192.168.2.135/eportal/success.jsp?"
  
  # 你的校园网账号（通常是学号）
  username: "your_student_id"
  
  # 你的密码（首次运行后会自动加密保存）
  password: "your_password"
  
  # 如果登录页需要额外的表单字段，在这里添加
  extra_fields: {}
    # service: ""
    # queryString: ""

keepalive:
  # 心跳间隔（秒）
  # 建议设置为校园网超时时间的 1/3
  # 例如：超时 30 分钟 -> 间隔 120 秒（2 分钟）
  interval_seconds: 120
  
  # 心跳检测目标 URL
  targets:
    - "http://www.baidu.com"
    - "http://connect.rom.miui.com/generate_204"

auto_login:
  # 是否启用自动重新登录
  enabled: true
  
  # 登录失败时最大重试次数
  max_retries: 3
  
  # 重试间隔（秒）
  retry_delay_seconds: 5

logging:
  # 日志级别: DEBUG, INFO, WARNING, ERROR
  level: "INFO"
  
  # 单个日志文件最大大小（MB）
  max_size_mb: 5
  
  # 保留的历史日志文件数量
  backup_count: 3
"""
        
        with open(example_path, 'w', encoding='utf-8') as f:
            f.write(example_content)
        
        self.logger.info(f"Example config created: {example_path}")
        return example_path


# 全局配置管理器
_manager: Optional[ConfigManager] = None
_config: Optional[AppConfig] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager


def get_config() -> AppConfig:
    """获取全局配置（加载一次后缓存）"""
    global _config
    if _config is None:
        _config = get_config_manager().load()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = get_config_manager().load()
    return _config


if __name__ == '__main__':
    # 测试
    manager = ConfigManager()
    
    # 创建示例配置
    example_path = manager.create_example()
    print(f"Created example config: {example_path}")
    
    # 加载配置（使用默认值）
    config = manager.load()
    print(f"\nLoaded config:")
    print(f"  Portal URL: {config.portal.login_url or '(not set)'}")
    print(f"  Username: {config.portal.username or '(not set)'}")
    print(f"  Interval: {config.keepalive.interval_seconds}s")
    print(f"  Auto-login: {config.auto_login.enabled}")
    
    # 测试加密
    if HAS_CRYPTO:
        test_password = "test123"
        encrypted = manager.encrypt_password(test_password)
        decrypted = manager.decrypt_password(encrypted)
        print(f"\nEncryption test:")
        print(f"  Original: {test_password}")
        print(f"  Encrypted: {encrypted[:30]}...")
        print(f"  Decrypted: {decrypted}")
        print(f"  Match: {test_password == decrypted}")
    else:
        print("\nNote: cryptography not installed, password encryption disabled")
