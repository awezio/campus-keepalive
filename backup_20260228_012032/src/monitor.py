#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campus Network Timeout Monitor
校园网超时检测脚本

Purpose: 检测校园网在无网络活动后多久会自动断开连接

Mode:
  active  默认。每隔 interval 秒发一次 HTTP 请求做检测 → 会产生网络活动，无法测出真实超时。
  silent  静默模式。每个周期只在「周期开始」和「周期结束」各检测一次，中间整段时间不发任何请求，
          用于测定真实超时时间。建议 interval 设长（如 2100=35分钟）。
  ladder  梯级模式。从短间隔开始逐步增长，自动探测超时临界值。从 start_interval 开始，
          每次通过后按 multiplier 增长，直到断网或达到 max_interval。

Usage:
    python monitor.py --mode silent --interval 2100   # 静默：每35分钟只做2次检测，中间零请求
    python monitor.py --mode ladder                 # 梯级：从30分钟开始自动增长直到断网
    python monitor.py --mode active --interval 60  # 主动：每60秒检测一次（会保活，测不出超时）
    python monitor.py --analyze                     # 分析已收集的日志数据
"""

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Optional, List, Dict

try:
    import requests
except ImportError:
    print("Error: requests 库未安装，请运行: pip install requests")
    sys.exit(1)


# 配置常量
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "monitor.csv"
CSV_HEADERS = ["timestamp", "status", "response_code", "response_time_ms", "redirect_url", "notes"]

# 检测目标 URL（使用 HTTP 而非 HTTPS，因为 HTTPS 无法被网关重定向）
CHECK_URLS = [
    ("http://www.baidu.com", "baidu"),
    ("http://connect.rom.miui.com/generate_204", "miui_204"),
    ("http://www.qq.com", "qq"),
]

# 网络状态
STATUS_ONLINE = "ONLINE"
STATUS_OFFLINE = "OFFLINE"  # 被网关踢出，重定向到登录页
STATUS_ERROR = "ERROR"      # 网络异常（超时、DNS 失败等）

# 全局变量
running = True


def signal_handler(signum, frame):
    """处理 Ctrl+C 信号"""
    global running
    print("\n\n正在停止监控...")
    running = False


def ensure_log_dir():
    """确保日志目录存在"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def init_csv_log():
    """初始化 CSV 日志文件"""
    ensure_log_dir()
    if not LOG_FILE.exists():
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def check_single_url(url: str, timeout: int = 10) -> Tuple[str, int, float, Optional[str], str]:
    """
    检测单个 URL 的网络状态

    Returns:
        Tuple of (status, response_code, response_time_ms, redirect_url, notes)
    """
    start_time = time.time()

    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=False,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

        response_time = (time.time() - start_time) * 1000
        status_code = response.status_code

        if status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get('Location', '')
            login_keywords = ['login', 'portal', 'auth', '认证', '登录', '10.', '192.168.', '172.']
            is_login_redirect = any(kw in redirect_url.lower() for kw in login_keywords)

            if is_login_redirect:
                return (STATUS_OFFLINE, status_code, response_time, redirect_url, "Redirected to login portal")
            else:
                return (STATUS_ONLINE, status_code, response_time, redirect_url, "Normal redirect")

        elif status_code == 200:
            return (STATUS_ONLINE, status_code, response_time, None, "OK")

        elif status_code == 204:
            return (STATUS_ONLINE, status_code, response_time, None, "No Content (expected)")

        else:
            return (STATUS_ERROR, status_code, response_time, None, f"Unexpected status: {status_code}")

    except requests.exceptions.Timeout:
        response_time = (time.time() - start_time) * 1000
        return (STATUS_ERROR, 0, response_time, None, "Request timeout")

    except requests.exceptions.ConnectionError as e:
        response_time = (time.time() - start_time) * 1000
        return (STATUS_ERROR, 0, response_time, None, f"Connection error: {str(e)[:50]}")

    except requests.exceptions.RequestException as e:
        response_time = (time.time() - start_time) * 1000
        return (STATUS_ERROR, 0, response_time, None, f"Request error: {str(e)[:50]}")


def check_network_status(timeout: int = 10) -> Tuple[str, int, float, Optional[str], str]:
    """检测网络状态，依次尝试多个 URL"""
    for url, name in CHECK_URLS:
        status, code, resp_time, redirect, notes = check_single_url(url, timeout)

        if status in (STATUS_ONLINE, STATUS_OFFLINE):
            return (status, code, resp_time, redirect, f"[{name}] {notes}")

    return (STATUS_ERROR, 0, 0, None, f"All URLs failed. Last: {notes}")


def log_result(timestamp: datetime, status: str, code: int, resp_time: float,
               redirect: Optional[str], notes: str, silent_console: bool = False):
    """记录检测结果到 CSV 和控制台"""
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp.isoformat(),
            status,
            code,
            f"{resp_time:.1f}",
            redirect or "",
            notes
        ])

    if not silent_console:
        status_icon = {"ONLINE": "✓", "OFFLINE": "✗", "ERROR": "!"}.get(status, "?")
        status_color = {"ONLINE": "\033[92m", "OFFLINE": "\033[91m", "ERROR": "\033[93m"}.get(status, "")
        reset = "\033[0m"
        print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
              f"{status_color}{status_icon} {status:8}{reset} | "
              f"Code: {code:3} | Time: {resp_time:6.1f}ms | {notes}")


def analyze_logs() -> Dict:
    """分析日志文件，计算超时时间"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return {}

    print(f"\n{'='*60}")
    print("校园网超时分析报告")
    print(f"{'='*60}\n")

    records = []
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['timestamp'] = datetime.fromisoformat(row['timestamp'])
            records.append(row)

    if not records:
        print("日志文件为空")
        return {}

    total = len(records)
    online_count = sum(1 for r in records if r['status'] == STATUS_ONLINE)
    offline_count = sum(1 for r in records if r['status'] == STATUS_OFFLINE)
    error_count = sum(1 for r in records if r['status'] == STATUS_ERROR)
    first_time = records[0]['timestamp']
    last_time = records[-1]['timestamp']
    duration = last_time - first_time

    print(f"监控时间段: {first_time.strftime('%Y-%m-%d %H:%M:%S')} 至 {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总监控时长: {duration}")
    print(f"总记录数: {total} (ONLINE: {online_count}, OFFLINE: {offline_count}, ERROR: {error_count})")

    disconnections = []
    last_online_time = None
    for i, record in enumerate(records):
        if record['status'] == STATUS_ONLINE:
            last_online_time = record['timestamp']
        elif record['status'] == STATUS_OFFLINE and last_online_time:
            idle_duration = record['timestamp'] - last_online_time
            disconnections.append({
                'offline_time': record['timestamp'],
                'last_online_time': last_online_time,
                'idle_duration': idle_duration,
                'redirect_url': record.get('redirect_url', '')
            })
            last_online_time = None

    print(f"\n{'-'*60}\n断网事件分析:\n{'-'*60}")
    if not disconnections:
        print("未检测到断网事件。")
        print("可能原因: 1) 监控时间不够 2) 使用了 active 模式，检测请求本身在保活")
        print("建议: 使用 --mode silent --interval 2100 做静默测量")
    else:
        for i, disc in enumerate(disconnections, 1):
            print(f"  [{i}] 断网: {disc['offline_time'].strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"上次在线: {disc['last_online_time'].strftime('%H:%M:%S')} | "
                  f"空闲时长: {disc['idle_duration']}")
        idle_secs = [d['idle_duration'].total_seconds() for d in disconnections]
        min_idle = min(idle_secs)
        avg_idle = sum(idle_secs) / len(idle_secs)
        recommended = int(min_idle / 3)
        print(f"\n最短空闲断网: {timedelta(seconds=min_idle)} | 平均: {timedelta(seconds=avg_idle)}")
        print(f"【推荐心跳间隔】: {recommended} 秒 ({recommended//60} 分钟)")

    print(f"\n{'='*60}\n")
    return {'total_records': total, 'disconnections': disconnections, 'duration': duration}


def run_monitor_active(interval: int, silent_console: bool = False):
    """主动模式：每隔 interval 秒发一次请求检测（会产生网络活动，会保活）"""
    global running
    init_csv_log()
    print(f"\n{'='*60}\n校园网超时监控 [主动模式]\n{'='*60}")
    print(f"检测间隔: {interval} 秒（每次检测都会发请求，会保持连接活跃）")
    print(f"日志: {LOG_FILE}\n按 Ctrl+C 停止\n{'='*60}\n")

    check_count = 0
    last_status = None
    last_status_change_time = datetime.now()

    while running:
        timestamp = datetime.now()
        status, code, resp_time, redirect, notes = check_network_status()

        if last_status and status != last_status:
            notes += f" | Status changed from {last_status} after {timestamp - last_status_change_time}"
            last_status_change_time = timestamp

        log_result(timestamp, status, code, resp_time, redirect, notes, silent_console)
        last_status = status
        check_count += 1

        if status == STATUS_OFFLINE and not silent_console:
            print(f"\n{'!'*60}\n!!! 检测到断网 - 网关已将连接重定向到登录页 !!!\n{'!'*60}\n")

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break

    print(f"\n监控已停止。共完成 {check_count} 次检测。")
    print(f"运行 'python monitor.py --analyze' 分析数据")


def run_monitor_silent(interval: int, silent_console: bool = False):
    """
    静默模式：每个周期只在周期开始和周期结束各检测一次，中间整段时间不发任何网络请求。
    用于测定「无活动多久会被踢下线」的真实超时时间。
    """
    global running
    init_csv_log()
    idle_min = interval / 60.0
    print(f"\n{'='*60}\n校园网超时监控 [静默模式]\n{'='*60}")
    print(f"每个周期: 先检测 1 次 → 静默 {interval} 秒（零请求）→ 再检测 1 次")
    print(f"即每 {idle_min:.1f} 分钟内仅 2 次请求，中间不产生任何网络活动")
    print(f"日志: {LOG_FILE}\n按 Ctrl+C 停止\n{'='*60}\n")

    cycle = 0
    while running:
        cycle += 1
        # 周期开始：检测一次（唯一会产生流量的时刻之一）
        t0 = datetime.now()
        status0, code0, time0, redirect0, notes0 = check_network_status()
        log_result(t0, status0, code0, time0, redirect0, notes0, silent_console)

        if status0 == STATUS_OFFLINE and not silent_console:
            print(f"\n!!! 当前已离线，静默 {interval}s 后将再次检测 !!!\n")

        # 静默期：不发送任何请求
        if not silent_console:
            print(f"[周期 {cycle}] 进入静默期 {interval} 秒，不发送任何请求...")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break

        if not running:
            break

        # 周期结束：再检测一次
        t1 = datetime.now()
        status1, code1, time1, redirect1, notes1 = check_network_status()
        log_result(t1, status1, code1, time1, redirect1, notes1, silent_console)

        if status0 == STATUS_ONLINE and status1 == STATUS_OFFLINE and not silent_console:
            print(f"\n{'!'*60}")
            print(f"!!! 在静默 {interval}s 后检测到断网 → 推测超时时间 ≤ {idle_min:.1f} 分钟 !!!")
            print(f"{'!'*60}\n")

    print(f"\n静默监控已停止。共完成 {cycle} 个周期。")
    print(f"运行 'python monitor.py --analyze' 分析数据")


def run_monitor_ladder(start_interval: int = 1800, multiplier: float = 1.5,
                       max_interval: int = 10800, silent_console: bool = False):
    """
    梯级模式：从短间隔开始逐步增长，自动探测超时临界值。

    工作流程：
    1. 从 start_interval 开始（默认 1800 秒 = 30 分钟）
    2. 每个周期静默 interval 秒，然后检测
    3. 如果通过（ONLINE），按 multiplier 增长间隔（默认 ×1.5）
    4. 如果断网（OFFLINE）或达到 max_interval，停止并报告结果

    Args:
        start_interval: 初始静默间隔（秒），默认 1800（30 分钟）
        multiplier: 增长倍数，默认 1.5（每次增加 50%）
        max_interval: 最大间隔限制（秒），默认 10800（3 小时）
        silent_console: 是否静默控制台输出
    """
    global running
    init_csv_log()
    start_min = start_interval / 60.0
    max_min = max_interval / 60.0

    print(f"\n{'='*60}\n校园网超时监控 [梯级模式]\n{'='*60}")
    print(f"初始间隔: {start_interval} 秒 ({start_min:.1f} 分钟)")
    print(f"增长倍数: {multiplier}x")
    print(f"最大间隔: {max_interval} 秒 ({max_min:.1f} 分钟)")
    print(f"工作流程: 从短间隔开始 → 每次通过后增长 → 直到断网或达到最大值")
    print(f"日志: {LOG_FILE}\n按 Ctrl+C 停止\n{'='*60}\n")

    current_interval = start_interval
    last_success_interval = 0
    cycle = 0

    while running:
        cycle += 1
        current_min = current_interval / 60.0

        if not silent_console:
            print(f"\n{'─'*60}")
            print(f"[周期 {cycle}] 当前间隔: {current_interval} 秒 ({current_min:.1f} 分钟)")
            print(f"{'─'*60}")

        # 周期开始：检测一次
        t0 = datetime.now()
        status0, code0, time0, redirect0, notes0 = check_network_status()
        log_result(t0, status0, code0, time0, redirect0, notes0, silent_console)

        if status0 == STATUS_OFFLINE:
            if not silent_console:
                print(f"\n!!! 当前已离线，需要先重新登录校园网 !!!")
            break

        # 静默期：不发送任何请求
        if not silent_console:
            print(f"进入静默期 {current_interval} 秒，不发送任何请求...")
        try:
            time.sleep(current_interval)
        except KeyboardInterrupt:
            print("\n\n用户中断")
            break

        if not running:
            break

        # 周期结束：再检测一次
        t1 = datetime.now()
        status1, code1, time1, redirect1, notes1 = check_network_status()
        log_result(t1, status1, code1, time1, redirect1, notes1, silent_console)

        if status0 == STATUS_ONLINE and status1 == STATUS_ONLINE:
            # 通过：记录并增长间隔
            last_success_interval = current_interval
            if not silent_console:
                print(f"✓ 检测通过 - 静默 {current_interval} 秒后仍在线")

            # 检查是否达到最大值
            if current_interval >= max_interval:
                if not silent_console:
                    print(f"\n{'='*60}")
                    print(f"!!! 已达到最大间隔 {max_interval} 秒 ({max_min:.1f} 分钟) 且仍未断网 !!!")
                    print(f"结论: 校园网超时时间 > {max_min:.1f} 分钟")
                    print(f"建议: 可以继续增大 max_interval 进行测试")
                    print(f"{'='*60}\n")
                break

            # 增长间隔
            new_interval = min(int(current_interval * multiplier), max_interval)
            if not silent_console:
                print(f"下一个周期: {new_interval} 秒 ({new_interval/60:.1f} 分钟)")
            current_interval = new_interval

        elif status0 == STATUS_ONLINE and status1 == STATUS_OFFLINE:
            # 断网：找到临界点
            if last_success_interval > 0:
                last_min = last_success_interval / 60.0
                if not silent_console:
                    print(f"\n{'!'*60}")
                    print(f"!!! 在静默 {current_interval} 秒 ({current_min:.1f} 分钟) 后检测到断网 !!!")
                    print(f"{'!'*60}")
                    print(f"\n结论: 超时时间在 {last_min:.1f} ~ {current_min:.1f} 分钟之间")
                    print(f"      上次通过: {last_success_interval} 秒 ({last_min:.1f} 分钟)")
                    print(f"      本次断网: {current_interval} 秒 ({current_min:.1f} 分钟)")
                    print(f"\n【推荐心跳间隔】: {int(last_success_interval / 3)} 秒 ({int(last_success_interval / 3 / 60)} 分钟)")
                    print(f"{'='*60}\n")
            else:
                if not silent_console:
                    print(f"\n{'!'*60}")
                    print(f"!!! 第一个周期 ({current_interval} 秒) 就断网了 !!!")
                    print(f"结论: 超时时间 ≤ {current_min:.1f} 分钟")
                    print(f"建议: 减小 start_interval 重新测试")
                    print(f"{'='*60}\n")
            break

        else:
            # 其他情况（例如一开始就离线）
            if not silent_console:
                print(f"\n异常状态: 开始={status0}, 结束={status1}")
            break

    print(f"\n梯级监控已停止。共完成 {cycle} 个周期。")
    print(f"运行 'python monitor.py --analyze' 查看详细日志")

def main():
    parser = argparse.ArgumentParser(
        description='校园网超时检测脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor.py --mode silent --interval 2100   # 静默：每35分钟仅2次检测，测真实超时
  python monitor.py --mode ladder                 # 梯级：自动探测超时临界值（推荐）
  python monitor.py --mode active --interval 60     # 主动：每60秒检测（会保活）
  python monitor.py --analyze                       # 分析日志
        """
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['silent', 'active', 'ladder'],
        default='active',
        help='silent=只监测不保活; ladder=自动增长探测超时(推荐); active=每隔 interval 检测一次(会保活)'
    )
    parser.add_argument('--interval', '-i', type=int, default=60, help='检测间隔（秒）；静默模式建议 2100（35分钟）')
    parser.add_argument('--start-interval', type=int, default=1800, help='梯级模式：初始间隔（秒），默认 1800（30分钟）')
    parser.add_argument('--multiplier', type=float, default=1.5, help='梯级模式：增长倍数，默认 1.5x')
    parser.add_argument('--max-interval', type=int, default=10800, help='梯级模式：最大间隔（秒），默认 10800（3小时）')
    parser.add_argument('--silent', '-s', action='store_true', help='静默控制台输出（仍写日志）')
    parser.add_argument('--analyze', '-a', action='store_true', help='分析已收集的日志数据')
    parser.add_argument('--timeout', '-t', type=int, default=10, help='单次请求超时（秒）')

    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)

    if args.analyze:
        analyze_logs()
    elif args.mode == 'ladder':
        run_monitor_ladder(args.start_interval, args.multiplier, args.max_interval, args.silent)
    elif args.mode == 'silent':
        run_monitor_silent(args.interval, args.silent)
    else:
        run_monitor_active(args.interval, args.silent)


if __name__ == '__main__':
    main()
