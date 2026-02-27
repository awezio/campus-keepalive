#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Tray Icon Module
系统托盘图标模块

功能:
- 在 Windows 系统托盘显示图标
- 右键菜单操作
- 状态显示（在线/离线/重连中）
"""

import sys
import threading
from enum import Enum
from typing import Callable, Optional
from pathlib import Path

from logger_setup import get_main_logger


class TrayStatus(Enum):
    """托盘图标状态"""
    ONLINE = "online"       # 在线 - 绿色
    OFFLINE = "offline"     # 离线 - 红色
    CONNECTING = "connecting"  # 连接中 - 黄色
    PAUSED = "paused"       # 已暂停 - 灰色


class TrayIcon:
    """系统托盘图标"""
    
    APP_NAME = "校园网保活"
    
    # 图标颜色
    COLORS = {
        TrayStatus.ONLINE: (46, 204, 113),      # 绿色
        TrayStatus.OFFLINE: (231, 76, 60),      # 红色
        TrayStatus.CONNECTING: (241, 196, 15),  # 黄色
        TrayStatus.PAUSED: (149, 165, 166),     # 灰色
    }
    
    def __init__(
        self,
        on_quit: Optional[Callable] = None,
        on_pause: Optional[Callable] = None,
        on_resume: Optional[Callable] = None,
        on_reconnect: Optional[Callable] = None,
        on_show_log: Optional[Callable] = None,
        on_config: Optional[Callable] = None,
    ):
        """
        初始化托盘图标

        Args:
            on_quit: 点击退出时的回调
            on_pause: 点击暂停时的回调
            on_resume: 点击恢复时的回调
            on_reconnect: 点击重新连接时的回调
            on_show_log: 点击查看日志时的回调
            on_config: 点击配置时的回调
        """
        self.on_quit = on_quit
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_reconnect = on_reconnect
        self.on_show_log = on_show_log
        self.on_config = on_config
        """
        初始化托盘图标
        
        Args:
            on_quit: 点击退出时的回调
            on_pause: 点击暂停时的回调
            on_resume: 点击恢复时的回调
            on_reconnect: 点击重新连接时的回调
            on_show_log: 点击查看日志时的回调
        """
        self.on_quit = on_quit
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_reconnect = on_reconnect
        self.on_show_log = on_show_log
        
        self.logger = get_main_logger()
        self._icon = None
        self._status = TrayStatus.ONLINE
        self._paused = False
        self._available = False
        
        # 尝试导入 pystray
        try:
            import pystray
            from PIL import Image
            self._pystray = pystray
            self._Image = Image
            self._available = True
            self.logger.debug("Pystray initialized successfully")
        except ImportError as e:
            self.logger.warning(f"pystray not available: {e}")
    
    def is_available(self) -> bool:
        """检查托盘功能是否可用"""
        return self._available
    
    def _create_icon_image(self, status: TrayStatus):
        """创建指定状态的图标图像"""
        color = self.COLORS.get(status, self.COLORS[TrayStatus.ONLINE])
        
        # 创建一个 64x64 的圆形图标
        size = 64
        image = self._Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # 绘制圆形
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        
        # 外圆（边框）
        padding = 2
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=color,
            outline=(255, 255, 255)
        )
        
        # 内圆（高光效果）
        inner_padding = size // 4
        lighter_color = tuple(min(255, c + 50) for c in color)
        draw.ellipse(
            [inner_padding, inner_padding, size - inner_padding, size - inner_padding],
            fill=lighter_color
        )
        
        return image
    
    def _get_status_text(self) -> str:
        """获取当前状态文本"""
        texts = {
            TrayStatus.ONLINE: "在线",
            TrayStatus.OFFLINE: "离线",
            TrayStatus.CONNECTING: "连接中...",
            TrayStatus.PAUSED: "已暂停",
        }
        return texts.get(self._status, "未知")
    
    def _create_menu(self):
        """创建右键菜单"""
        from pystray import MenuItem, Menu
        
        def action_quit(icon, item):
            self.logger.info("Tray: Quit clicked")
            if self.on_quit:
                self.on_quit()
            self.stop()
        
        def action_pause_resume(icon, item):
            if self._paused:
                self.logger.info("Tray: Resume clicked")
                self._paused = False
                if self.on_resume:
                    self.on_resume()
            else:
                self.logger.info("Tray: Pause clicked")
                self._paused = True
                if self.on_pause:
                    self.on_pause()
            self._update_menu()
        
        def action_reconnect(icon, item):
            self.logger.info("Tray: Reconnect clicked")
            if self.on_reconnect:
                self.on_reconnect()
        
        def action_show_log(icon, item):
            self.logger.info("Tray: Show log clicked")
            if self.on_show_log:
                self.on_show_log()
            else:
                # 默认：打开日志目录
                import os
                import subprocess
                log_dir = Path(__file__).parent.parent / "logs"
                if sys.platform == 'win32':
                    os.startfile(log_dir)
                else:
                    subprocess.Popen(['xdg-open', str(log_dir)])
        
        def action_config(icon, item):
            self.logger.info("Tray: Config clicked")
            if self.on_config:
                self.on_config()
        
        pause_text = "恢复保活" if self._paused else "暂停保活"
        
        return Menu(
            MenuItem(f"状态: {self._get_status_text()}", lambda: None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(pause_text, action_pause_resume),
            MenuItem("立即重连", action_reconnect),
            Menu.SEPARATOR,
            MenuItem("查看日志", action_show_log),
            MenuItem("配置", action_config),
            Menu.SEPARATOR,
            MenuItem("退出", action_quit),
        )
    
    def _update_menu(self):
        """更新菜单（需要重新创建图标）"""
        if self._icon:
            self._icon.menu = self._create_menu()
    
    def set_status(self, status: TrayStatus):
        """
        设置托盘图标状态
        
        Args:
            status: 新状态
        """
        if status == self._status:
            return
        
        self._status = status
        self.logger.debug(f"Tray status changed to: {status.value}")
        
        if self._icon:
            self._icon.icon = self._create_icon_image(status)
            self._icon.title = f"{self.APP_NAME} - {self._get_status_text()}"
            self._update_menu()
    
    def start(self):
        """启动托盘图标（在主线程或新线程中运行）"""
        if not self._available:
            self.logger.warning("Tray icon not available")
            return
        
        try:
            self._icon = self._pystray.Icon(
                name=self.APP_NAME,
                icon=self._create_icon_image(self._status),
                title=f"{self.APP_NAME} - {self._get_status_text()}",
                menu=self._create_menu()
            )
            
            self.logger.info("Starting tray icon...")
            self._icon.run()
            
        except Exception as e:
            self.logger.error(f"Failed to start tray icon: {e}")
    
    def start_detached(self):
        """在后台线程中启动托盘图标"""
        if not self._available:
            return
        
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
    
    def stop(self):
        """停止托盘图标"""
        if self._icon:
            self.logger.info("Stopping tray icon...")
            self._icon.stop()
            self._icon = None


# 全局托盘图标
_tray: Optional[TrayIcon] = None


def get_tray() -> TrayIcon:
    """获取全局托盘图标"""
    global _tray
    if _tray is None:
        _tray = TrayIcon()
    return _tray


def init_tray(
    on_quit: Optional[Callable] = None,
    on_pause: Optional[Callable] = None,
    on_resume: Optional[Callable] = None,
    on_reconnect: Optional[Callable] = None,
    on_show_log: Optional[Callable] = None,
    on_config: Optional[Callable] = None,
) -> TrayIcon:
    """
    初始化托盘图标
    
    Args:
        on_quit: 退出回调
        on_pause: 暂停回调
        on_resume: 恢复回调
        on_reconnect: 重连回调
        on_show_log: 查看日志回调
        on_config: 配置回调
    
    Returns:
        TrayIcon 实例
    """
    global _tray
    _tray = TrayIcon(
        on_quit=on_quit,
        on_pause=on_pause,
        on_resume=on_resume,
        on_reconnect=on_reconnect,
        on_show_log=on_show_log,
        on_config=on_config,
    )
    return _tray
    
    

if __name__ == '__main__':
    # 测试托盘图标
    import time
    
    def on_quit():
        print("Quit clicked!")
    
    def on_pause():
        print("Paused!")
        tray.set_status(TrayStatus.PAUSED)
    
    def on_resume():
        print("Resumed!")
        tray.set_status(TrayStatus.ONLINE)
    
    def on_reconnect():
        print("Reconnecting...")
        tray.set_status(TrayStatus.CONNECTING)
        time.sleep(2)
        tray.set_status(TrayStatus.ONLINE)
    
    tray = TrayIcon(
        on_quit=on_quit,
        on_pause=on_pause,
        on_resume=on_resume,
        on_reconnect=on_reconnect
    )
    
    if tray.is_available():
        print("Starting tray icon test...")
        print("Right-click the tray icon to see the menu")
        print("Press Ctrl+C to exit")
        
        # 在后台线程启动托盘
        tray.start_detached()
        
        # 模拟状态变化
        try:
            time.sleep(3)
            print("Setting status to CONNECTING...")
            tray.set_status(TrayStatus.CONNECTING)
            
            time.sleep(3)
            print("Setting status to ONLINE...")
            tray.set_status(TrayStatus.ONLINE)
            
            time.sleep(3)
            print("Setting status to OFFLINE...")
            tray.set_status(TrayStatus.OFFLINE)
            
            # 保持运行
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping...")
            tray.stop()
    else:
        print("Tray icon not available")
        print("Install: pip install pystray pillow")
