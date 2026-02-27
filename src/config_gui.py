#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config GUI Module
配置界面模块

使用 tkinter 创建 GUI 配置窗口，替代外部 config.yaml 文件。
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
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

from config_manager import AppConfig, PortalConfig, ConfigManager, get_config_manager
from portal_detector import PortalDetector
from logger_setup import get_main_logger


class ConfigGUI:
    """配置界面"""

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
        self.window.title("校园网保活 - 配置")
        self.window.geometry("600x500")
        self.window.resizable(False, False)

        # 尝试设置图标
        self._set_window_icon()

        self.on_save = on_save
        self.config_manager = get_config_manager()
        self.logger = get_main_logger()
        self.portal_detector = PortalDetector()

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
            main_frame, text="校园网登录配置", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 创建可滚动的笔记本
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 基本配置页面
        basic_frame = ttk.Frame(notebook, padding="10")
        notebook.add(basic_frame, text="基本配置")
        self._create_basic_config(basic_frame)

        # 高级配置页面
        advanced_frame = ttk.Frame(notebook, padding="10")
        notebook.add(advanced_frame, text="高级配置")
        self._create_advanced_config(advanced_frame)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 按钮按钮
        ttk.Button(button_frame, text="自动检测登录页", command=self._auto_detect).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="测试登录", command=self._test_login).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10
        )
        ttk.Button(button_frame, text="取消", command=self.window.destroy).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(button_frame, text="保存", command=self._save_config).pack(
            side=tk.RIGHT, padx=5
        )

    def _create_basic_config(self, parent: ttk.Frame):
        """创建基本配置页面"""
        # 登录页 URL
        url_frame = ttk.Frame(parent)
        url_frame.pack(fill=tk.X, pady=5)

        ttk.Label(url_frame, text="登录页 URL:").pack(anchor=tk.W)
        url_entry_frame = ttk.Frame(url_frame)
        url_entry_frame.pack(fill=tk.X, pady=(5, 0))

        self.login_url_var = tk.StringVar()
        self.login_url_entry = ttk.Entry(
            url_entry_frame, textvariable=self.login_url_var, width=50
        )
        self.login_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            url_entry_frame, text="检测", width=8, command=self._auto_detect
        ).pack(side=tk.LEFT, padx=(5, 0))

        # 用户名
        username_frame = ttk.Frame(parent)
        username_frame.pack(fill=tk.X, pady=5)

        ttk.Label(username_frame, text="学号/用户名:").pack(anchor=tk.W)
        self.username_var = tk.StringVar()
        ttk.Entry(username_frame, textvariable=self.username_var, width=50).pack(
            fill=tk.X, pady=(5, 0)
        )

        # 密码
        password_frame = ttk.Frame(parent)
        password_frame.pack(fill=tk.X, pady=5)

        ttk.Label(password_frame, text="密码:").pack(anchor=tk.W)
        password_entry_frame = ttk.Frame(password_frame)
        password_entry_frame.pack(fill=tk.X, pady=(5, 0))

        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            password_entry_frame, textvariable=self.password_var, width=50, show="*"
        )
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            password_entry_frame, text="显示", width=8, command=self._toggle_password
        ).pack(side=tk.LEFT, padx=(5, 0))

        # 心跳间隔
        interval_frame = ttk.Frame(parent)
        interval_frame.pack(fill=tk.X, pady=5)

        ttk.Label(interval_frame, text="心跳间隔（秒）:").pack(anchor=tk.W)
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

        # 自动登录开关
        self.auto_login_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            parent, text="启用自动重新登录", variable=self.auto_login_var
        ).pack(anchor=tk.W, pady=5)

    def _create_advanced_config(self, parent: ttk.Frame):
        """创建高级配置页面"""
        # 登录失败重试次数
        retry_frame = ttk.Frame(parent)
        retry_frame.pack(fill=tk.X, pady=5)

        ttk.Label(retry_frame, text="登录失败重试次数:").pack(anchor=tk.W)
        self.max_retries_var = tk.IntVar(value=3)
        ttk.Spinbox(
            retry_frame, from_=1, to=10, textvariable=self.max_retries_var, width=10
        ).pack(anchor=tk.W, pady=(5, 0))

        # 重试间隔
        retry_delay_frame = ttk.Frame(parent)
        retry_delay_frame.pack(fill=tk.X, pady=5)

        ttk.Label(retry_delay_frame, text="重试间隔（秒）:").pack(anchor=tk.W)
        self.retry_delay_var = tk.IntVar(value=5)
        ttk.Spinbox(
            retry_delay_frame,
            from_=1,
            to=60,
            textvariable=self.retry_delay_var,
            width=10,
        ).pack(anchor=tk.W, pady=(5, 0))

        # 日志级别
        log_level_frame = ttk.Frame(parent)
        log_level_frame.pack(fill=tk.X, pady=5)

        ttk.Label(log_level_frame, text="日志级别:").pack(anchor=tk.W)
        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            log_level_frame,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=15,
        )
        log_level_combo.pack(anchor=tk.W, pady=(5, 0))

        # 说明文本
        help_text = """
提示：
- 心跳间隔建议设置为超时时间的 1/3
- 根据测试结果，默认心跳间隔为 3600 秒（1 小时）
- 日志级别 DEBUG 会记录详细信息，INFO 记录关键信息
- 网络异常时会自动重试登录
        """
        ttk.Label(parent, text=help_text, justify=tk.LEFT).pack(anchor=tk.W, pady=10)

    def _load_config(self):
        """加载配置到界面"""
        try:
            config = self.config_manager.load()
            self.current_config = config

            # 加载基本配置
            self.login_url_var.set(config.portal.login_url)
            self.username_var.set(config.portal.username)
            self.password_var.set(config.portal.password)
            self.interval_var.set(str(config.keepalive.interval_seconds))
            self.interval_label_var.set(
                f"{config.keepalive.interval_seconds} 秒 ({config.keepalive.interval_seconds // 60} 分钟)"
            )
            self.auto_login_var.set(config.auto_login.enabled)

            # 加载高级配置
            self.max_retries_var.set(config.auto_login.max_retries)
            self.retry_delay_var.set(config.auto_login.retry_delay_seconds)
            self.log_level_var.set(config.logging.level)

            self.logger.info("配置已加载到界面")

        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            messagebox.showerror("错误", f"加载配置失败: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            # 验证输入
            if not self.login_url_var.get().strip():
                messagebox.showwarning("警告", "请输入登录页 URL")
                return

            if not self.username_var.get().strip():
                messagebox.showwarning("警告", "请输入学号/用户名")
                return

            if not self.password_var.get().strip():
                messagebox.showwarning("警告", "请输入密码")
                return

            # 创建配置对象
            config = AppConfig()
            config.portal = PortalConfig(
                login_url=self.login_url_var.get().strip(),
                username=self.username_var.get().strip(),
                password=self.password_var.get().strip(),
                extra_fields={},
            )

            config.keepalive.interval_seconds = int(self.interval_var.get())
            config.auto_login.enabled = self.auto_login_var.get()
            config.auto_login.max_retries = self.max_retries_var.get()
            config.auto_login.retry_delay_seconds = self.retry_delay_var.get()
            config.logging.level = self.log_level_var.get()

            # 保存配置
            self.config_manager.save(config, encrypt_password=True)

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

    def _auto_detect(self):
        """自动检测校园网登录页"""

        def detect_thread():
            try:
                self.login_url_entry.config(state=tk.DISABLED)

                needs_login, login_url = self.portal_detector.detect_portal()

                if needs_login and login_url:
                    self.login_url_var.set(login_url)
                    self.logger.info(f"检测到登录页: {login_url}")
                    messagebox.showinfo(
                        "检测成功", f"已检测到校园网登录页:\n{login_url}"
                    )
                elif not needs_login:
                    self.logger.info("网络正常，不需要登录")
                    messagebox.showinfo("检测结果", "当前网络正常，不需要登录")
                else:
                    self.logger.warning("无法确定登录页 URL")
                    messagebox.showwarning("检测失败", "无法确定登录页 URL，请手动输入")

            except Exception as e:
                self.logger.error(f"检测失败: {e}")
                messagebox.showerror("错误", f"检测失败: {e}")
            finally:
                self.login_url_entry.config(state=tk.NORMAL)

        # 在后台线程中运行检测
        threading.Thread(target=detect_thread, daemon=True).start()

    def _test_login(self):
        """测试登录"""
        try:
            from network_checker import NetworkChecker, NetworkStatus

            checker = NetworkChecker()
            result = checker.check()

            if result.status == NetworkStatus.ONLINE:
                messagebox.showinfo("测试结果", f"网络状态：在线 ✓\n\n{result.message}")
            elif result.status == NetworkStatus.OFFLINE:
                messagebox.showwarning("测试结果", f"网络状态：离线（需要登录）\n\n{result.message}")
                if result.redirect_url:
                    messagebox.showinfo("登录页", f"检测到登录页：\n{result.redirect_url}")
            else:
                messagebox.showerror("测试结果", f"网络状态：{result.status.value}\n\n{result.message}")

        except Exception as e:
            self.logger.error(f"测试登录失败: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"测试失败: {e}")

    def _toggle_password(self):
        """切换密码显示/隐藏"""
        if self.password_entry.cget("show") == "*":
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

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
