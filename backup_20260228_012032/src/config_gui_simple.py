#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config GUI Module - Simple Version
配置界面模块（简化版 - 仅保活配置）

使用 tkinter 创建 GUI 配置窗口。
本版本不包含自动登录相关配置。
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional, Callable
import sys

# 添加 src 目录到路径
if getattr(sys, "frozen", False):
    # EXE 环境
    BASE_DIR = Path(sys.executable).parent
else:
    # 开发环境
    BASE_DIR = Path(__file__).parent.parent

sys.path.insert(0, str(BASE_DIR))

from config_manager import AppConfig, ConfigManager, get_config_manager
from logger_setup import get_main_logger


class ConfigGUI:
    """配置界面（简化版）"""

    def __init__(
        self, parent: Optional[tk.Tk] = None, on_save: Optional[Callable] = None
    ):
        """
        初始化配置界面

        Args:
            parent: 父窗口
            on_save: 配置保存后的回调函数
        """
        self.window = parent or tk.Tk()
        self.window.title("校园网保活 - 配置（仅保活）")
        self.window.geometry("500x350")
        self.window.resizable(False, False)
        
        # 尝试设置图标
        self._set_window_icon()

        self.on_save = on_save
        self.config_manager = get_config_manager()
        self.logger = get_main_logger()

        # 当前配置
        self.current_config: Optional[AppConfig] = None

        # 创建界面
        self._create_widgets()

        # 加载配置
        self._load_config()
    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_path = BASE_DIR / "assets" / "icon.ico"
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(
            main_frame, text="校园网保活配置", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 说明
        info_text = """
本版本仅提供保活功能，不包含自动登录。
请确保 Windows WiFi 自动登录功能已启用。

保活功能：定时发送心跳请求，防止校园网因
长时间无活动而自动断开连接。
        """
        ttk.Label(main_frame, text=info_text, justify=tk.LEFT, foreground="#666").pack(
            anchor=tk.W, pady=(0, 20)
        )

        # 心跳间隔
        interval_frame = ttk.Frame(main_frame)
        interval_frame.pack(fill=tk.X, pady=10)

        ttk.Label(
            interval_frame, text="心跳间隔（秒）:", font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        interval_info_frame = ttk.Frame(interval_frame)
        interval_info_frame.pack(fill=tk.X, pady=(5, 0))

        self.interval_var = tk.StringVar()
        ttk.Scale(
            interval_info_frame,
            from_=60,
            to=3600,
            variable=self.interval_var,
            command=lambda v: self.interval_label_var.set(
                f"{int(float(v))} 秒 ({int(float(v)) // 60} 分钟)"
            ),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.interval_label_var = tk.StringVar(value="600 秒 (10 分钟)")
        ttk.Label(
            interval_info_frame, textvariable=self.interval_label_var, width=20
        ).pack(side=tk.LEFT, padx=(5, 0))

        # 日志级别
        log_level_frame = ttk.Frame(main_frame)
        log_level_frame.pack(fill=tk.X, pady=10)

        ttk.Label(log_level_frame, text="日志级别:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W
        )
        log_level_combo_frame = ttk.Frame(log_level_frame)
        log_level_combo_frame.pack(fill=tk.X, pady=(5, 0))

        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            log_level_combo_frame,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=15,
        )
        log_level_combo.pack(anchor=tk.W, pady=(0, 0))

        # 帮助文本
        help_text = """
提示：
• 心跳间隔建议设置为 60-3600 秒（1 分钟到 1 小时）
• 根据测试结果，校园网 3 小时内未断网
• 建议心跳间隔：1800 秒（30 分钟）- 3600 秒（1 小时）
• 日志级别 DEBUG 记录详细信息，INFO 记录关键信息
• 保活请求非常轻量，几乎不消耗带宽
        """
        ttk.Label(main_frame, text=help_text, justify=tk.LEFT, foreground="#888").pack(
            anchor=tk.W, pady=(20, 0)
        )

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="取消", command=self.window.destroy).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(button_frame, text="保存", command=self._save_config).pack(
            side=tk.RIGHT, padx=5
        )

    def _load_config(self):
        """加载配置到界面"""
        try:
            config = self.config_manager.load()
            self.current_config = config

            # 加载心跳间隔
            self.interval_var.set(str(config.keepalive.interval_seconds))
            self.interval_label_var.set(
                f"{config.keepalive.interval_seconds} 秒 ({config.keepalive.interval_seconds // 60} 分钟)"
            )

            # 加载日志级别
            self.log_level_var.set(config.logging.level)

            self.logger.info("配置已加载到界面")

        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            messagebox.showerror("错误", f"加载配置失败: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            # 创建配置对象（保持原有配置）
            config = self.config_manager.load()

            # 更新心跳间隔
            config.keepalive.interval_seconds = int(self.interval_var.get())

            # 更新日志级别
            config.logging.level = self.log_level_var.get()

            # 保存配置
            self.config_manager.save(config, encrypt_password=False)  # 不需要加密密码

            self.logger.info("配置已保存")
            messagebox.showinfo("成功", "配置已保存！")

            # 调用回调
            if self.on_save:
                self.on_save(config)

            # 关闭窗口
            self.window.destroy()

        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def show(self):
        """显示配置界面"""
        self.window.mainloop()


    def destroy(self):
        """关闭窗口"""
        self.window.destroy()


def show_config_dialog(
    parent: Optional[tk.Tk] = None, on_save: Optional[Callable] = None
):
    """
    显示配置对话框

    Args:
        parent: 父窗口
        on_save: 配置保存后的回调函数
    """
    gui = ConfigGUI(parent, on_save)
    gui.show()


if __name__ == "__main__":
    # 测试
    show_config_dialog()
