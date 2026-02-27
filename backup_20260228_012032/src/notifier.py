#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notifier Module
Windows 通知模块

功能:
- 发送 Windows Toast 通知
- 支持不同优先级和图标
"""

import sys
from typing import Optional
from enum import Enum

from logger_setup import get_main_logger


class NotifyLevel(Enum):
    """通知级别"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Notifier:
    """Windows 通知器"""
    
    APP_ID = "CampusNetworkKeepAlive"
    APP_NAME = "校园网保活"
    
    def __init__(self):
        """初始化通知器"""
        self.logger = get_main_logger()
        self._toast = None
        self._available = False
        
        # 尝试导入 winotify
        try:
            from winotify import Notification, audio
            self._toast_class = Notification
            self._audio = audio
            self._available = True
            self.logger.debug("Winotify initialized successfully")
        except ImportError:
            self.logger.warning("winotify not available, notifications disabled")
        except Exception as e:
            self.logger.warning(f"Failed to initialize winotify: {e}")
    
    def is_available(self) -> bool:
        """检查通知功能是否可用"""
        return self._available
    
    def notify(
        self,
        title: str,
        message: str,
        level: NotifyLevel = NotifyLevel.INFO,
        duration: str = "short"
    ) -> bool:
        """
        发送通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            duration: 显示时长 ("short" 或 "long")
        
        Returns:
            是否发送成功
        """
        if not self._available:
            self.logger.info(f"[Notification] {title}: {message}")
            return False
        
        try:
            from winotify import Notification
            
            toast = Notification(
                app_id=self.APP_NAME,
                title=title,
                msg=message,
                duration=duration
            )
            
            # 根据级别设置音效
            if level == NotifyLevel.ERROR:
                toast.set_audio(self._audio.LoopingAlarm, loop=False)
            elif level == NotifyLevel.WARNING:
                toast.set_audio(self._audio.Reminder, loop=False)
            elif level == NotifyLevel.SUCCESS:
                toast.set_audio(self._audio.IM, loop=False)
            else:
                toast.set_audio(self._audio.Default, loop=False)
            
            toast.show()
            self.logger.debug(f"Notification sent: {title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False
    
    def notify_online(self):
        """通知：网络已连接"""
        self.notify(
            title="网络已连接",
            message="校园网连接正常",
            level=NotifyLevel.SUCCESS
        )
    
    def notify_offline(self, redirect_url: Optional[str] = None):
        """通知：网络已断开"""
        message = "检测到校园网已断开"
        if redirect_url:
            message += f"\n正在尝试自动重新登录..."
        
        self.notify(
            title="网络断开",
            message=message,
            level=NotifyLevel.WARNING
        )
    
    def notify_login_success(self):
        """通知：登录成功"""
        self.notify(
            title="登录成功",
            message="已自动重新连接校园网",
            level=NotifyLevel.SUCCESS
        )
    
    def notify_login_failed(self, reason: str = ""):
        """通知：登录失败"""
        message = "自动登录失败"
        if reason:
            message += f": {reason}"
        message += "\n请手动登录校园网"
        
        self.notify(
            title="登录失败",
            message=message,
            level=NotifyLevel.ERROR,
            duration="long"
        )
    
    def notify_service_started(self):
        """通知：服务已启动"""
        self.notify(
            title="保活服务已启动",
            message="校园网保活程序正在后台运行",
            level=NotifyLevel.INFO
        )
    
    def notify_service_stopped(self):
        """通知：服务已停止"""
        self.notify(
            title="保活服务已停止",
            message="校园网保活程序已退出",
            level=NotifyLevel.INFO
        )


# 全局通知器
_notifier: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """获取全局通知器"""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


if __name__ == '__main__':
    # 测试通知
    notifier = Notifier()
    
    print(f"Notification available: {notifier.is_available()}")
    
    if notifier.is_available():
        print("Sending test notifications...")
        
        notifier.notify("测试通知", "这是一条普通通知", NotifyLevel.INFO)
        
        import time
        time.sleep(2)
        
        notifier.notify_online()
        
        time.sleep(2)
        
        notifier.notify_offline("http://10.0.0.1/login")
        
        print("Done!")
    else:
        print("Install winotify: pip install winotify")
