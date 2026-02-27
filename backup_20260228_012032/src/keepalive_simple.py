#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campus Network Keep-Alive - Simple Version
校园网保活主程序（简化版，仅保活功能）

功能：
- 定期心跳保持网络活跃
- 检测断网并通知
- 系统托盘后台运行
- Windows 通知提醒

说明：
- 本版本不包含自动登录功能
- 依赖 Windows WiFi 自动登录功能
- 仅用于防止校园网因长时间无活动而断开
"""

import argparse
import sys
import threading
import time
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from logger_setup import get_main_logger
from config_manager import AppConfig, PortalConfig, get_config_manager
from network_checker import NetworkChecker, NetworkStatus, CheckResult
from heartbeat import Heartbeat, HeartbeatStats
from notifier import Notifier, get_notifier
from tray_icon import TrayIcon, TrayStatus, init_tray
from config_gui_simple import ConfigGUI  # 显式导入配置界面模块


class KeepAliveService:
    """校园网保活服务（简化版）"""

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
        self.tray: TrayIcon = None

        # 状态
        self._running = False
        self._stop_event = threading.Event()

        # 统计
        self._start_time = None

    def _init_heartbeat(self):
        """初始化心跳服务"""
        self.heartbeat = Heartbeat(
            interval=self.config.keepalive.interval_seconds,
            targets=self.config.keepalive.targets,
            on_offline=self._on_offline,
            on_online=self._on_online,
            on_error=self._on_error,
        )

    def _init_tray(self):
        """初始化托盘图标"""
        self.tray = init_tray(
            on_quit=self.stop,
            on_pause=self._on_pause,
            on_resume=self._on_resume,
            on_show_log=self._on_show_log,
            on_config=self._on_config,
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

        # 本版本不包含自动登录，提示用户
        self.logger.warning("请手动登录校园网")
        self.notifier.notify_login_failed("请手动登录校园网")

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

    def _on_show_log(self):
        """托盘菜单：查看日志"""
        import os
        from pathlib import Path
        from logger_setup import get_base_dir

        log_dir = get_base_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(log_dir)])

    def _on_config(self):
        """托盘菜单：配置"""
        self._show_config_dialog()

    def _show_config_dialog(self):
        """显示配置对话框"""

        def on_config_saved(config):
            """配置保存后的回调"""
            self.logger.info("Config updated, reloading...")
            # 重新加载配置
            from config_manager import reload_config

            self.config = reload_config()
            # 重新初始化心跳
            self._init_heartbeat()

        try:
            import tkinter as tk

            # 创建配置窗口（不传入 parent，让 ConfigGUI 自己创建窗口）
            gui = ConfigGUI(on_save=on_config_saved)
            gui.show()

        except Exception as e:
            self.logger.error(f"Failed to show config dialog: {e}")
            import traceback

            traceback.print_exc()

    def start(self, with_tray: bool = True):
        """
        启动保活服务

        Args:
            with_tray: 是否显示系统托盘图标
        """
        if self._running:
            self.logger.warning("Service already running")
            return

        self._running = True
        self._start_time = time.time()
        self._stop_event.clear()

        self.logger.info("=" * 60)
        self.logger.info("Campus Network Keep-Alive Service Starting (Simple Version)")
        self.logger.info("=" * 60)
        self.logger.info(
            f"心跳间隔: {self.config.keepalive.interval_seconds}秒 ({self.config.keepalive.interval_seconds // 60} 分钟)"
        )
        self.logger.info(
            f"注意: 本版本不包含自动登录功能，请确保 Windows WiFi 自动登录已启用"
        )

        # 初始化各模块
        self._init_heartbeat()

        if with_tray:
            self._init_tray()

        # 检查初始网络状态
        self.logger.info("Checking initial network status...")
        result = self.checker.check()

        if result.status == NetworkStatus.ONLINE:
            self.logger.info("Network is online")
            if self.tray:
                self.tray.set_status(TrayStatus.ONLINE)
        elif result.status == NetworkStatus.OFFLINE:
            self.logger.warning("Network is offline")
            if self.tray:
                self.tray.set_status(TrayStatus.OFFLINE)
            self.notifier.notify_login_failed("请手动登录校园网")
        else:
            self.logger.error(f"Network check failed: {result.message}")

        # 启动心跳服务
        self.heartbeat.start()

        # 发送启动通知
        self.notifier.notify_service_started()

        self.logger.info("Service started successfully")
        self.logger.info("右键托盘图标可暂停/配置")

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
        self.logger.info(f"  运行时长: {uptime / 3600:.1f} 小时")
        self.logger.info(f"  总心跳次数: {stats.total_beats}")
        self.logger.info(f"  成功次数: {stats.successful_beats}")
        self.logger.info(f"  失败次数: {stats.failed_beats}")
        self.logger.info("=" * 60)

        self.logger.info("Service stopped")


def setup_signal_handlers(service: KeepAliveService):
    """设置信号处理器"""

    def signal_handler(signum, frame):
        print("\nReceived stop signal...")
        service.stop()
        sys.exit(0)

    import signal

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, signal_handler)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="校园网保活工具（简化版 - 仅保活功能）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

示例:
  python keepalive.py              # 启动保活服务
  python keepalive.py --check     # 只检查网络状态
  python keepalive.py --interval 3600  # 使用自定义心跳间隔
        """,
    )

    parser.add_argument("--check", action="store_true", help="只检查网络状态")
    parser.add_argument("--interval", "-i", type=int, help="心跳间隔（秒）")
    parser.add_argument("--no-tray", action="store_true", help="不显示系统托盘图标")

    args = parser.parse_args()

    # 加载配置
    config_manager = get_config_manager()
    config = config_manager.load()

    # 如果指定了心跳间隔，覆盖配置
    if args.interval:
        config.keepalive.interval_seconds = args.interval

    # 如果是检查模式
    if args.check:
        checker = NetworkChecker()
        result = checker.check()

        print(f"\n网络状态: {result.status.value}")
        print(f"响应码: {result.response_code}")
        print(f"响应时间: {result.response_time_ms:.1f}ms")
        print(f"重定向URL: {result.redirect_url or 'N/A'}")
        print(f"信息: {result.message}")

        if result.status == NetworkStatus.ONLINE:
            print("\n[OK] 网络在线")
        elif result.status == NetworkStatus.OFFLINE:
            print("\n[ERROR] 网络离线（需要登录）")
            if result.redirect_url:
                print(f"登录页: {result.redirect_url}")
        else:
            print(f"\n[WARN] 网络检测异常")

        return

    # 启动保活服务
    service = KeepAliveService(config)
    setup_signal_handlers(service)
    service.start(with_tray=not args.no_tray)


if __name__ == "__main__":
    main()
