#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campus Network Keep-Alive Main Program
校园网保活主程序

功能:
- 定期心跳保持网络活跃
- 检测断网并自动重新登录
- 系统托盘后台运行
- Windows 通知提醒
"""

import argparse
import signal
import sys
import threading
import time
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from logger_setup import setup_logger, get_main_logger
from config_manager import ConfigManager, AppConfig, get_config
from network_checker import NetworkChecker, NetworkStatus, CheckResult
from heartbeat import Heartbeat, HeartbeatStats
from auto_login import AutoLogin, LoginResult
from notifier import Notifier, get_notifier
from tray_icon import TrayIcon, TrayStatus, init_tray


class KeepAliveService:
    """校园网保活服务"""
    
    def __init__(self, config: AppConfig):
        """
        初始化保活服务
        
        Args:
            config: 应用配置
        """
        self.config = config
        self.logger = get_main_logger()
        
        # 初始化各模块
        self.checker = NetworkChecker()
        self.notifier = get_notifier()
        self.heartbeat: Heartbeat = None
        self.auto_login: AutoLogin = None
        self.tray: TrayIcon = None
        
        # 状态
        self._running = False
        self._reconnecting = False
        self._stop_event = threading.Event()
        
        # 统计
        self._reconnect_count = 0
        self._start_time = None
    
    def _init_heartbeat(self):
        """初始化心跳服务"""
        self.heartbeat = Heartbeat(
            interval=self.config.keepalive.interval_seconds,
            targets=self.config.keepalive.targets,
            on_offline=self._on_offline,
            on_online=self._on_online,
            on_error=self._on_error
        )
    
    def _init_auto_login(self):
        """初始化自动登录模块"""
        if not self.config.portal.login_url:
            self.logger.warning("Login URL not configured, auto-login disabled")
            return
        
        self.auto_login = AutoLogin(
            login_url=self.config.portal.login_url,
            username=self.config.portal.username,
            password=self.config.portal.password,
            extra_fields=self.config.portal.extra_fields
        )
        
        # 预先分析登录页面
        self.auto_login.analyze_login_page()
    
    def _init_tray(self):
        """初始化托盘图标"""
        self.tray = init_tray(
            on_quit=self.stop,
            on_pause=self._on_pause,
            on_resume=self._on_resume,
            on_reconnect=self._on_reconnect,
            on_show_log=self._on_show_log,
            on_config=self._on_config
        )
    def _on_online(self, result: CheckResult):
        """心跳检测到在线的回调"""
        if self.tray:
            self.tray.set_status(TrayStatus.ONLINE)
    
    def _on_offline(self, result: CheckResult):
        """心跳检测到离线的回调"""
        self.logger.warning(f"Network offline detected: {result.message}")
        
        if self.tray:
            self.tray.set_status(TrayStatus.OFFLINE)
        
        # 发送通知
        self.notifier.notify_offline(result.redirect_url)
        
        # 尝试自动重新登录
        if self.config.auto_login.enabled and self.auto_login:
            self._do_reconnect()
    
    def _on_error(self, result: CheckResult):
        """心跳检测出错的回调"""
        self.logger.error(f"Network check error: {result.message}")
    
    def _on_pause(self):
        """托盘菜单：暂停"""
        if self.heartbeat:
            self.heartbeat.pause()
        if self.tray:
            self.tray.set_status(TrayStatus.PAUSED)
        self.logger.info("Keep-alive paused")
    
    def _on_resume(self):
        """托盘菜单：恢复"""
        if self.heartbeat:
            self.heartbeat.resume()
        if self.tray:
            self.tray.set_status(TrayStatus.ONLINE)
        self.logger.info("Keep-alive resumed")
    
    def _on_reconnect(self):
        """托盘菜单：立即重连"""
        self._do_reconnect()
    
    def _do_reconnect(self):
        """执行重新连接"""
        if self._reconnecting:
            self.logger.info("Reconnection already in progress")
            return
        
        if not self.auto_login:
            self.logger.warning("Auto-login not configured")
            self.notifier.notify_login_failed("未配置自动登录")
            return
        
        self._reconnecting = True
        
        if self.tray:
            self.tray.set_status(TrayStatus.CONNECTING)
        
        self.logger.info("Attempting auto-login...")
        
        try:
            result = self.auto_login.login_with_retry(
                max_retries=self.config.auto_login.max_retries,
                delay=self.config.auto_login.retry_delay_seconds
            )
            
            if result.success:
                self._reconnect_count += 1
                self.logger.info(f"Auto-login successful (total: {self._reconnect_count})")
                self.notifier.notify_login_success()
                
                if self.tray:
                    self.tray.set_status(TrayStatus.ONLINE)
            else:
                self.logger.error(f"Auto-login failed: {result.message}")
                self.notifier.notify_login_failed(result.message)
                
                if self.tray:
                    self.tray.set_status(TrayStatus.OFFLINE)
                    
                # 登录失败，提示配置
                self._show_config_dialog("登录失败，请检查配置")
                    
        except Exception as e:
            self.logger.error(f"Auto-login exception: {e}")
            self.notifier.notify_login_failed(str(e))
            
            if self.tray:
                self.tray.set_status(TrayStatus.OFFLINE)
        
    
    def _on_show_log(self):
        """托盘菜单：查看日志"""
        import os
        from pathlib import Path
        from logger_setup import get_base_dir
        
        log_dir = get_base_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        if sys.platform == 'win32':
            os.startfile(log_dir)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', str(log_dir)])
    
    def _on_config(self):
        """托盘菜单：配置"""
        self._show_config_dialog()
    
    def _show_config_dialog(self, message: str = ""):
        """
        显示配置对话框

        Args:
            message: 可选的提示信息
        """
        def on_config_saved(config):
            """配置保存后的回调"""
            self.logger.info("Config updated, reloading...")
            # 重新加载配置
            from config_manager import reload_config
            self.config = reload_config()
            # 重新初始化模块
            self._init_heartbeat()
            self._init_auto_login()
        try:
            import tkinter as tk
            from config_gui import ConfigGUI
            
            # 如果有消息，先显示
            if message:
                from tkinter import messagebox
                messagebox.showwarning("提示", message)
            
            # 暂停心跳
            if self.heartbeat:
                self.heartbeat.pause()
            
            # 创建配置窗口（不传入 parent，让 ConfigGUI 自己创建窗口）
            gui = ConfigGUI(on_save=on_config_saved)
            gui.show()
            
            # 恢复心跳
            if self.heartbeat:
                self.heartbeat.resume()
                
        except Exception as e:
            self.logger.error(f"Failed to show config dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_config(self) -> bool:
        """
        检查配置是否完整

        Returns:
            True 如果配置完整，False 否则
        """
        # 检查必要字段
        required_fields = {
            'login_url': self.config.portal.login_url,
            'username': self.config.portal.username,
            'password': self.config.portal.password,
        }
        
        missing_fields = [name for name, value in required_fields.items() if not value or value.strip() == '']
        
        if missing_fields:
            self.logger.warning(f"Missing required fields: {missing_fields}")
            self._show_config_dialog("请配置校园网登录信息")
            return False
        
        return True
    
    def start(self, with_tray: bool = True):
        """
        启动保活服务
        
        Args:
            with_tray: 是否显示系统托盘图标
        """
        self._running = True
        self._start_time = time.time()
        self._stop_event.clear()
        
        # 检查配置是否完整
        if not self._check_config():
            self.logger.warning("Configuration incomplete")
            return False
        
        self.logger.info("=" * 60)
        self.logger.info("Campus Network Keep-Alive Service Starting")
        self.logger.info("=" * 60)
        self.logger.info(f"Heartbeat interval: {self.config.keepalive.interval_seconds}s")
        self.logger.info(f"Auto-login enabled: {self.config.auto_login.enabled}")
        
        # 初始化各模块
        self._init_heartbeat()
        self._init_auto_login()
        # 初始化各模块
        self._init_heartbeat()
        self._init_auto_login()
        
        if with_tray:
            self._init_tray()
        
        # 首先检查当前网络状态
        self.logger.info("Checking initial network status...")
        result = self.checker.check()
        
        if result.status == NetworkStatus.ONLINE:
            self.logger.info("Network is online")
            if self.tray:
                self.tray.set_status(TrayStatus.ONLINE)
        elif result.status == NetworkStatus.OFFLINE:
            self.logger.warning("Network is offline, attempting login...")
            self._do_reconnect()
        else:
            self.logger.error(f"Network check failed: {result.message}")
        
        # 启动心跳服务
        self.heartbeat.start()
        
        # 发送启动通知
        self.notifier.notify_service_started()
        
        self.logger.info("Service started successfully")
        self.logger.info("Press Ctrl+C to stop")
        
        # 启动托盘图标（这会阻塞主线程）
        if with_tray and self.tray and self.tray.is_available():
            self.tray.start()
        else:
            # 无托盘模式：等待停止信号
            try:
                while self._running:
                    self._stop_event.wait(timeout=1)
            except KeyboardInterrupt:
                pass
    
    def stop(self):
        """停止保活服务"""
        if not self._running:
            return
        
        self.logger.info("Stopping service...")
        self._running = False
        self._stop_event.set()
        
        # 停止心跳
        if self.heartbeat:
            self.heartbeat.stop()
        
        # 停止托盘
        if self.tray:
            self.tray.stop()
        
        # 发送通知
        self.notifier.notify_service_stopped()
        
        # 打印统计
        uptime = time.time() - self._start_time if self._start_time else 0
        stats = self.heartbeat.get_stats() if self.heartbeat else HeartbeatStats()
        
        self.logger.info("=" * 60)
        self.logger.info("Service Statistics:")
        self.logger.info(f"  Uptime: {uptime/3600:.1f} hours")
        self.logger.info(f"  Total heartbeats: {stats.total_beats}")
        self.logger.info(f"  Successful: {stats.successful_beats}")
        self.logger.info(f"  Failed: {stats.failed_beats}")
        self.logger.info(f"  Auto-reconnects: {self._reconnect_count}")
        self.logger.info("=" * 60)
        
        self.logger.info("Service stopped")


def setup_signal_handlers(service: KeepAliveService):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        print("\nReceived stop signal...")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)


def main():
    parser = argparse.ArgumentParser(
        description='校园网保活程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python keepalive.py                  # 正常启动（带托盘图标）
  python keepalive.py --no-tray        # 不显示托盘图标
  python keepalive.py --interval 300   # 设置心跳间隔为 300 秒
  python keepalive.py --check          # 只检测一次网络状态
  python keepalive.py --login          # 只执行一次登录
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        help='心跳间隔（秒），覆盖配置文件'
    )
    
    parser.add_argument(
        '--no-tray',
        action='store_true',
        help='不显示系统托盘图标'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='只检测一次网络状态并退出'
    )
    
    parser.add_argument(
        '--login',
        action='store_true',
        help='只执行一次登录操作并退出'
    )
    
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='创建示例配置文件'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    import logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger("keepalive", "keepalive.log", level=log_level)
    
    # 创建示例配置
    if args.create_config:
        manager = ConfigManager()
        path = manager.create_example()
        print(f"Created example config: {path}")
        print("Please copy it to config.yaml and edit with your settings")
        return
    
    # 加载配置
    config_path = Path(args.config) if args.config else None
    manager = ConfigManager(config_path)
    config = manager.load()
    
    # 覆盖配置
    if args.interval:
        config.keepalive.interval_seconds = args.interval
    
    # 只检测网络状态
    if args.check:
        checker = NetworkChecker()
        result = checker.check()
        print(f"Status: {result.status.value}")
        print(f"Code: {result.response_code}")
        print(f"Time: {result.response_time_ms:.1f}ms")
        print(f"Redirect: {result.redirect_url or 'N/A'}")
        print(f"Message: {result.message}")
        return
    
    # 只执行登录
    if args.login:
        if not config.portal.login_url:
            print("Error: login_url not configured")
            return
        
        login = AutoLogin(
            login_url=config.portal.login_url,
            username=config.portal.username,
            password=config.portal.password,
            extra_fields=config.portal.extra_fields
        )
        
        print(f"Logging in to {config.portal.login_url}...")
        result = login.login()
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        return
    
    # 启动服务
    service = KeepAliveService(config)
    setup_signal_handlers(service)
    
    try:
        service.start(with_tray=not args.no_tray)
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
