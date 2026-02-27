#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Heartbeat Module
心跳保活模块

功能:
- 定期发送轻量级 HTTP 请求保持网络活跃
- 防止校园网网关因超时断开连接
"""

import threading
import time
from typing import Callable, Optional, List
from dataclasses import dataclass

try:
    import requests
except ImportError:
    raise ImportError("请安装 requests: pip install requests")

from logger_setup import get_main_logger
from network_checker import NetworkChecker, NetworkStatus, CheckResult


@dataclass
class HeartbeatStats:
    """心跳统计信息"""
    total_beats: int = 0
    successful_beats: int = 0
    failed_beats: int = 0
    last_beat_time: Optional[float] = None
    last_beat_status: Optional[NetworkStatus] = None
    start_time: Optional[float] = None


class Heartbeat:
    """心跳保活服务"""
    
    # 默认心跳目标（轻量级 URL）
    DEFAULT_TARGETS = [
        "http://www.baidu.com",
        "http://connect.rom.miui.com/generate_204",
    ]
    
    def __init__(
        self,
        interval: int = 600,  # 默认 10 分钟
        targets: Optional[List[str]] = None,
        on_offline: Optional[Callable[[CheckResult], None]] = None,
        on_online: Optional[Callable[[CheckResult], None]] = None,
        on_error: Optional[Callable[[CheckResult], None]] = None,
    ):
        """
        初始化心跳服务
        
        Args:
            interval: 心跳间隔（秒）
            targets: 心跳目标 URL 列表
            on_offline: 检测到离线时的回调函数
            on_online: 检测到在线时的回调函数（每次心跳后）
            on_error: 检测出错时的回调函数
        """
        self.interval = interval
        self.targets = targets or self.DEFAULT_TARGETS
        self.on_offline = on_offline
        self.on_online = on_online
        self.on_error = on_error
        
        self.logger = get_main_logger()
        self.checker = NetworkChecker()
        self.stats = HeartbeatStats()
        
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def _do_heartbeat(self) -> CheckResult:
        """执行一次心跳"""
        result = self.checker.check()
        
        self.stats.total_beats += 1
        self.stats.last_beat_time = time.time()
        self.stats.last_beat_status = result.status
        
        if result.status == NetworkStatus.ONLINE:
            self.stats.successful_beats += 1
            self.logger.info(f"Heartbeat OK: {result.message} ({result.response_time_ms:.0f}ms)")
            if self.on_online:
                self.on_online(result)
        
        elif result.status == NetworkStatus.OFFLINE:
            self.stats.failed_beats += 1
            self.logger.warning(f"Heartbeat OFFLINE: {result.message}")
            if self.on_offline:
                self.on_offline(result)
        
        else:
            self.stats.failed_beats += 1
            self.logger.error(f"Heartbeat ERROR: {result.message}")
            if self.on_error:
                self.on_error(result)
        
        return result
    
    def _run_loop(self):
        """心跳循环（在后台线程中运行）"""
        self.stats.start_time = time.time()
        self.logger.info(f"Heartbeat service started (interval: {self.interval}s)")
        
        while self._running:
            if not self._paused:
                try:
                    self._do_heartbeat()
                except Exception as e:
                    self.logger.error(f"Heartbeat exception: {e}")
            
            # 等待下一次心跳，支持提前停止
            self._stop_event.wait(timeout=self.interval)
            if self._stop_event.is_set():
                break
        
        self.logger.info("Heartbeat service stopped")
    
    def start(self):
        """启动心跳服务（后台线程）"""
        if self._running:
            self.logger.warning("Heartbeat service already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止心跳服务"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
    
    def pause(self):
        """暂停心跳（不停止线程）"""
        self._paused = True
        self.logger.info("Heartbeat paused")
    
    def resume(self):
        """恢复心跳"""
        self._paused = False
        self.logger.info("Heartbeat resumed")
    
    def is_running(self) -> bool:
        """检查心跳服务是否正在运行"""
        return self._running and not self._paused
    
    def beat_now(self) -> CheckResult:
        """立即执行一次心跳（不影响定时周期）"""
        return self._do_heartbeat()
    
    def set_interval(self, interval: int):
        """
        更新心跳间隔
        
        Args:
            interval: 新的间隔时间（秒）
        """
        self.interval = interval
        self.logger.info(f"Heartbeat interval updated to {interval}s")
    
    def get_stats(self) -> HeartbeatStats:
        """获取心跳统计信息"""
        return self.stats
    
    def get_uptime(self) -> float:
        """获取服务运行时长（秒）"""
        if self.stats.start_time:
            return time.time() - self.stats.start_time
        return 0


# 全局实例
_heartbeat: Optional[Heartbeat] = None


def get_heartbeat() -> Heartbeat:
    """获取全局 Heartbeat 实例"""
    global _heartbeat
    if _heartbeat is None:
        _heartbeat = Heartbeat()
    return _heartbeat


def init_heartbeat(
    interval: int = 600,
    on_offline: Optional[Callable] = None
) -> Heartbeat:
    """
    初始化全局心跳服务
    
    Args:
        interval: 心跳间隔（秒）
        on_offline: 离线回调
    
    Returns:
        Heartbeat 实例
    """
    global _heartbeat
    _heartbeat = Heartbeat(interval=interval, on_offline=on_offline)
    return _heartbeat


if __name__ == '__main__':
    import signal
    import sys
    
    # 测试心跳服务
    def on_offline(result):
        print(f"\n!!! OFFLINE: {result.redirect_url}")
    
    def on_online(result):
        print(f"Online: {result.message}")
    
    heartbeat = Heartbeat(
        interval=10,  # 测试用短间隔
        on_offline=on_offline,
        on_online=on_online
    )
    
    def signal_handler(sig, frame):
        print("\nStopping...")
        heartbeat.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Starting heartbeat test (interval: 10s)")
    print("Press Ctrl+C to stop\n")
    
    # 先执行一次立即心跳
    heartbeat.beat_now()
    
    # 启动后台心跳
    heartbeat.start()
    
    # 主线程等待
    while heartbeat.is_running():
        time.sleep(1)
