#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PySide6 desktop UI for Campus KeepAlive."""

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config_manager import AppConfig, AppSettings, AutoLoginConfig, ConfigManager, KeepaliveConfig, LoggingConfig, PortalConfig
from mode_decider import RuntimeMode
from resources import resource_path
from service_controller import RuntimeStatus, ServiceController


APP_NAME = "校园网保活"


class StatusBridge(QObject):
    status_changed = Signal(object)


class SettingsDialog(QDialog):
    """Configuration dialog backed by AppConfig."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowIcon(QIcon(str(resource_path("assets", "icon.ico"))))
        self.setMinimumWidth(520)
        self._config = replace(config)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.mode = QComboBox()
        self.mode.addItem("自动判断", RuntimeMode.AUTO.value)
        self.mode.addItem("仅保活", RuntimeMode.KEEPALIVE_ONLY.value)
        self.mode.addItem("自动登录", RuntimeMode.AUTO_LOGIN.value)
        self.mode.setCurrentIndex(max(0, self.mode.findData(config.app.mode)))

        self.login_url = QLineEdit(config.portal.login_url)
        self.login_url.setPlaceholderText("http://192.168.2.135/eportal/success.jsp?")
        self.username = QLineEdit(config.portal.username)
        self.password = QLineEdit(config.portal.password)
        self.password.setEchoMode(QLineEdit.Password)

        self.interval = QSpinBox()
        self.interval.setRange(60, 24 * 3600)
        self.interval.setSingleStep(60)
        self.interval.setSuffix(" 秒")
        self.interval.setValue(config.keepalive.interval_seconds)

        self.max_retries = QSpinBox()
        self.max_retries.setRange(1, 10)
        self.max_retries.setValue(config.auto_login.max_retries)

        self.retry_delay = QSpinBox()
        self.retry_delay.setRange(1, 120)
        self.retry_delay.setSuffix(" 秒")
        self.retry_delay.setValue(config.auto_login.retry_delay_seconds)

        self.start_minimized = QCheckBox("启动后最小化到托盘")
        self.start_minimized.setChecked(config.app.start_minimized)

        self.show_notifications = QCheckBox("显示系统通知")
        self.show_notifications.setChecked(config.app.show_notifications)

        self.auto_login_enabled = QCheckBox("允许自动登录")
        self.auto_login_enabled.setChecked(config.auto_login.enabled)

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText(config.logging.level)

        form.addRow("运行模式", self.mode)
        form.addRow("登录页 URL", self.login_url)
        form.addRow("用户名", self.username)
        form.addRow("密码", self.password)
        form.addRow("心跳间隔", self.interval)
        form.addRow("登录重试次数", self.max_retries)
        form.addRow("重试间隔", self.retry_delay)
        form.addRow("", self.auto_login_enabled)
        form.addRow("", self.start_minimized)
        form.addRow("", self.show_notifications)
        form.addRow("日志级别", self.log_level)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def config(self) -> AppConfig:
        config = AppConfig(
            app=AppSettings(
                mode=self.mode.currentData(),
                start_minimized=self.start_minimized.isChecked(),
                show_notifications=self.show_notifications.isChecked(),
            ),
            portal=PortalConfig(
                login_url=self.login_url.text().strip(),
                username=self.username.text().strip(),
                password=self.password.text(),
                extra_fields=dict(self._config.portal.extra_fields),
            ),
            keepalive=KeepaliveConfig(
                interval_seconds=self.interval.value(),
                targets=list(self._config.keepalive.targets),
            ),
            auto_login=AutoLoginConfig(
                enabled=self.auto_login_enabled.isChecked(),
                max_retries=self.max_retries.value(),
                retry_delay_seconds=self.retry_delay.value(),
            ),
            logging=LoggingConfig(
                level=self.log_level.currentText(),
                max_size_mb=self._config.logging.max_size_mb,
                backup_count=self._config.logging.backup_count,
            ),
        )
        return config


class MainWindow(QMainWindow):
    """Main PySide6 window and tray owner."""

    def __init__(self, config: AppConfig, config_manager: ConfigManager):
        super().__init__()
        self.config = config
        self.bridge = StatusBridge()
        self.bridge.status_changed.connect(self.apply_status)
        self.controller = ServiceController(config, on_status=self.bridge.status_changed.emit)
        self.config_manager = config_manager
        self._quitting = False
        self._last_status = RuntimeStatus()

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets", "icon.ico"))))
        self.resize(720, 520)

        self._build_ui()
        self._build_tray()
        self.apply_status(RuntimeStatus())
        self.controller.start()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QIcon(str(resource_path("assets", "icon.ico"))).pixmap(48, 48))
        title_box = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel("校园网连接状态、保活与自动登录控制")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_box)
        header.addStretch(1)
        layout.addLayout(header)

        status_group = QGroupBox("当前状态")
        grid = QGridLayout(status_group)
        self.status_label = QLabel("未知")
        self.status_label.setObjectName("statusPill")
        self.mode_label = QLabel("仅保活")
        self.last_check_label = QLabel("尚未检测")
        self.heartbeat_label = QLabel("0 / 0 / 0")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        grid.addWidget(QLabel("网络"), 0, 0)
        grid.addWidget(self.status_label, 0, 1)
        grid.addWidget(QLabel("模式"), 1, 0)
        grid.addWidget(self.mode_label, 1, 1)
        grid.addWidget(QLabel("最近检测"), 2, 0)
        grid.addWidget(self.last_check_label, 2, 1)
        grid.addWidget(QLabel("心跳统计"), 3, 0)
        grid.addWidget(self.heartbeat_label, 3, 1)
        grid.addWidget(QLabel("提示"), 4, 0)
        grid.addWidget(self.error_label, 4, 1)
        layout.addWidget(status_group)

        actions = QHBoxLayout()
        self.check_button = QPushButton("立即检测")
        self.reconnect_button = QPushButton("立即重连")
        self.pause_button = QPushButton("暂停")
        self.settings_button = QPushButton("设置")
        self.logs_button = QPushButton("查看日志")
        self.check_button.clicked.connect(self.controller.check_now)
        self.reconnect_button.clicked.connect(self.controller.reconnect_now)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.settings_button.clicked.connect(self.open_settings)
        self.logs_button.clicked.connect(self.open_logs)
        for button in (self.check_button, self.reconnect_button, self.pause_button, self.settings_button, self.logs_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("运行状态会显示在这里。详细日志可通过“查看日志”打开。")
        layout.addWidget(self.log_view, 1)

        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow { background: #f6f8fb; }
            QLabel#title { font-size: 22px; font-weight: 700; color: #152033; }
            QLabel#subtitle { color: #5c6b7a; }
            QGroupBox {
                background: white;
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                margin-top: 10px;
                padding: 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #344054; }
            QLabel#statusPill {
                color: white;
                background: #64748b;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: 700;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton:hover { background: #eef6ff; border-color: #8ec5ff; }
            QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }
            QTextEdit {
                background: #0f172a;
                color: #dbeafe;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, monospace;
            }
            """
        )

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._tray_icon("paused"))
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()

        show_action = QAction("打开主界面", self)
        show_action.triggered.connect(self.show_window)
        self.pause_action = QAction("暂停", self)
        self.pause_action.triggered.connect(self.toggle_pause)
        check_action = QAction("立即检测", self)
        check_action.triggered.connect(self.controller.check_now)
        reconnect_action = QAction("立即重连", self)
        reconnect_action.triggered.connect(self.controller.reconnect_now)
        logs_action = QAction("查看日志", self)
        logs_action.triggered.connect(self.open_logs)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)

        for action in (show_action, self.pause_action, check_action, reconnect_action, logs_action):
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _tray_icon(self, state: str) -> QIcon:
        return QIcon(str(resource_path("assets", "icons", f"tray-{state}.ico")))

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()

    def apply_status(self, status: RuntimeStatus):
        self._last_status = status
        busy = status.checking or status.reconnecting
        state = self._visual_state(status)
        self.tray.setIcon(self._tray_icon(state))
        self.tray.setToolTip(f"{APP_NAME} - {self._status_text(status)}")

        self.status_label.setText(self._status_text(status))
        self.status_label.setStyleSheet(f"background: {self._status_color(state)};")
        self.mode_label.setText(self._mode_text(status.mode))
        if status.last_check:
            self.last_check_label.setText(status.last_check.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.last_check_label.setText("尚未检测")
        self.heartbeat_label.setText(
            f"总计 {status.total_beats} / 成功 {status.successful_beats} / 失败 {status.failed_beats}"
        )
        self.error_label.setText(status.last_error or "运行正常")
        self.check_button.setDisabled(status.checking)
        self.reconnect_button.setDisabled(busy)
        self.settings_button.setDisabled(busy)
        self.pause_button.setText("恢复" if status.paused else "暂停")
        self.pause_action.setText("恢复" if status.paused else "暂停")
        self._append_status_line(status)

    def _append_status_line(self, status: RuntimeStatus):
        if status.last_check:
            text = f"{status.last_check:%H:%M:%S} | {self._status_text(status)} | {self._mode_text(status.mode)}"
            if status.last_error:
                text += f" | {status.last_error}"
            if self.log_view.toPlainText().splitlines()[-1:] != [text]:
                self.log_view.append(text)

    def _visual_state(self, status: RuntimeStatus) -> str:
        if status.paused:
            return "paused"
        if status.reconnecting or status.checking:
            return "connecting"
        network = str(status.network_status).lower()
        if network == "online":
            return "online"
        if network in {"offline", "portal", "disconnected", "error"}:
            return "offline"
        return "paused"

    def _status_text(self, status: RuntimeStatus) -> str:
        if status.paused:
            return "已暂停"
        if status.reconnecting:
            return "重连中"
        if status.checking:
            return "检测中"
        mapping = {
            "online": "在线",
            "offline": "需要登录",
            "portal": "需要登录",
            "disconnected": "网络断开",
            "error": "检测异常",
            "unknown": "未知",
        }
        return mapping.get(str(status.network_status).lower(), str(status.network_status))

    def _status_color(self, state: str) -> str:
        return {
            "online": "#22c55e",
            "connecting": "#eab308",
            "offline": "#ef4444",
            "paused": "#64748b",
        }.get(state, "#64748b")

    def _mode_text(self, mode: RuntimeMode) -> str:
        return {
            RuntimeMode.AUTO: "自动判断",
            RuntimeMode.KEEPALIVE_ONLY: "仅保活",
            RuntimeMode.AUTO_LOGIN: "自动登录",
        }.get(mode, str(mode))

    def toggle_pause(self):
        if self._last_status.paused:
            self.controller.resume()
        else:
            self.controller.pause()

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config = dialog.config()
            self.config_manager.save(self.config, encrypt_password=True)
            self.controller.update_config(self.config)
            self.controller.check_now()

    def open_logs(self):
        from logger_setup import get_base_dir

        path = get_base_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            import os

            os.startfile(path)
        else:
            QMessageBox.information(self, "日志目录", str(path))

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        if self._quitting:
            self.controller.stop()
            self.tray.hide()
            event.accept()
        else:
            event.ignore()
            self.hide()
            if self.config.app.show_notifications:
                self.tray.showMessage(APP_NAME, "程序仍在托盘中运行", QSystemTrayIcon.Information, 1800)

    def quit_app(self):
        self._quitting = True
        self.controller.stop()
        QApplication.instance().quit()


def run_app(config: AppConfig, config_manager: ConfigManager) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(resource_path("assets", "icon.ico"))))
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, APP_NAME, "当前系统未检测到可用托盘，程序仍会显示主窗口。")

    window = MainWindow(config, config_manager)
    if config.app.start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
    else:
        window.show()

    return app.exec()
