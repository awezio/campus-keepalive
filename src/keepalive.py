#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Campus Network KeepAlive entry point."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from logger_setup import setup_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校园网保活程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  KeepAlive.exe                         # 启动图形界面和系统托盘
  KeepAlive.exe --check                 # 只检测一次网络状态
  KeepAlive.exe --login                 # 只执行一次登录
  KeepAlive.exe --create-config         # 创建配置模板
  KeepAlive.exe --interval 300          # 本次启动覆盖心跳间隔
        """,
    )
    parser.add_argument("--config", "-c", type=str, help="配置文件路径")
    parser.add_argument("--interval", "-i", type=int, help="心跳间隔（秒），覆盖配置文件")
    parser.add_argument("--check", action="store_true", help="只检测一次网络状态并退出")
    parser.add_argument("--login", action="store_true", help="只执行一次登录操作并退出")
    parser.add_argument("--create-config", action="store_true", help="创建示例配置文件")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")
    return parser


def run_check() -> int:
    from network_checker import NetworkChecker

    result = NetworkChecker().check()
    print(f"Status: {result.status.value}")
    print(f"Code: {result.response_code}")
    print(f"Time: {result.response_time_ms:.1f}ms")
    print(f"Redirect: {result.redirect_url or 'N/A'}")
    print(f"Message: {result.message}")
    return 0


def run_login(config) -> int:
    from auto_login import AutoLogin

    if not config.portal.login_url:
        print("Error: login_url not configured")
        return 2

    login = AutoLogin(
        login_url=config.portal.login_url,
        username=config.portal.username,
        password=config.portal.password,
        extra_fields=config.portal.extra_fields,
    )
    print(f"Logging in to {config.portal.login_url}...")
    result = login.login()
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    return 0 if result.success else 1


def main() -> int:
    args = build_parser().parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger("keepalive", "keepalive.log", level=log_level)

    from config_manager import ConfigManager

    config_path = Path(args.config) if args.config else None
    manager = ConfigManager(config_path)

    if args.create_config:
        path = manager.create_example()
        print(f"Created example config: {path}")
        return 0

    config = manager.load()
    if args.interval:
        config.keepalive.interval_seconds = args.interval

    if args.check:
        return run_check()
    if args.login:
        return run_login(config)

    try:
        from pyside_app import run_app
    except ImportError as exc:
        logger.error("PySide6 UI is not available: %s", exc)
        print("Error: PySide6 UI is not available. Install dependencies or use packaged KeepAlive.exe.")
        return 2

    return run_app(config, manager)


if __name__ == "__main__":
    raise SystemExit(main())
