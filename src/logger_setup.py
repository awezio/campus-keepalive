#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logger Setup Module
日志配置模块

提供统一的日志配置，支持:
- 控制台输出（带颜色）
- 文件输出（滚动日志）
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def get_base_dir() -> Path:
    """
    获取程序基础目录。

    打包为 EXE 时使用可执行文件所在目录，
    开发环境时使用脚本所在目录。
    """
    if getattr(sys, 'frozen', False):
        # 打包后的 EXE
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent.parent


# 日志目录（相对于程序基础目录）
BASE_DIR = get_base_dir()
LOG_DIR = BASE_DIR / "logs"

class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[91m',     # 亮红色
        'CRITICAL': '\033[41m',  # 红色背景
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 保存原始 levelname
        original_levelname = record.levelname
        
        # 添加颜色
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # 格式化
        result = super().format(record)
        
        # 恢复原始 levelname（避免影响其他 handler）
        record.levelname = original_levelname
        
        return result


def setup_logger(
    name: str = "keepalive",
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    max_size_mb: int = 5,
    backup_count: int = 3,
    console_output: bool = True
) -> logging.Logger:
    """
    设置并返回一个配置好的 logger
    
    Args:
        name: Logger 名称
        log_file: 日志文件名（不含路径），如果为 None 则使用 name.log
        level: 日志级别
        max_size_mb: 单个日志文件最大大小（MB）
        backup_count: 保留的历史日志文件数量
        console_output: 是否输出到控制台
    
    Returns:
        配置好的 Logger 实例
    """
    # 确保日志目录存在
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 获取或创建 logger
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 文件处理器（滚动日志）
    if log_file is None:
        log_file = f"{name}.log"
    log_path = LOG_DIR / log_file
    
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = "keepalive") -> logging.Logger:
    """获取已配置的 logger（如果不存在则创建）"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# 预配置的 logger 实例
def get_main_logger() -> logging.Logger:
    """获取主程序 logger"""
    return setup_logger("keepalive", "keepalive.log")


def get_network_logger() -> logging.Logger:
    """获取网络检测 logger"""
    return setup_logger("network", "network.log")


def get_login_logger() -> logging.Logger:
    """获取登录模块 logger"""
    return setup_logger("login", "login.log")


if __name__ == '__main__':
    # 测试日志配置
    logger = setup_logger("test", "test.log", level=logging.DEBUG)
    
    logger.debug("这是一条 DEBUG 消息")
    logger.info("这是一条 INFO 消息")
    logger.warning("这是一条 WARNING 消息")
    logger.error("这是一条 ERROR 消息")
    logger.critical("这是一条 CRITICAL 消息")
    
    print(f"\n日志文件已写入: {LOG_DIR / 'test.log'}")
