# Campus Network Keep-Alive 校园网保活工具

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Windows](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![Android](https://img.shields.io/badge/Android-Coming%20Soon-orange?logo=android)

一个防止校园网 Web Portal 认证网关因长时间无网络活动而自动断开的保活工具

[功能特性](#功能特性) • [快速开始](#快速开始) • [常见问题](#常见问题) • [技术架构](#技术架构)

</div>

---

## 项目简介

Campus Network Keep-Alive 是一个校园网保活工具，用于解决校园网 Web Portal 认证网关的自动超时断开问题。许多高校的校园网系统会在用户长时间无网络活动后自动断开连接，本工具通过定时发送轻量级 HTTP 请求保持网络活跃，并能在检测到断网后自动重新登录。

## 功能特性

- **网络保活**: 定时发送轻量级 HTTP 请求，防止网关超时断开
- **智能超时检测**: 支持梯级模式自动探测校园网超时临界值
- **自动重登录**: 检测到断网后自动使用保存的凭据重新登录，支持多种校园网 Portal 类型
- **系统托盘**: 后台运行，托盘图标实时显示连接状态
- **Windows 通知**: 断网、重连时弹出 Toast 通知，及时提醒用户
- **日志记录**: 完整的运行日志，方便排查问题
- **密码加密**: 使用 AES 加密存储密码，保护账户安全
- **图形配置**: 提供图形界面配置界面，无需手动编辑配置文件

## 快速开始

### Windows 版本

#### Phase 1: 检测超时时间

首次使用前，需要先运行监控脚本确定校园网「无活动多久会断网」。

```powershell
cd "D:\keep online"
pip install -r requirements.txt

# 梯级模式：从 30 分钟开始，自动增长直到断网（推荐）
python src/monitor.py --mode ladder
```

**梯级模式参数**:
- `--start-interval 1800`: 初始间隔 1800 秒（30 分钟）
- `--multiplier 1.5`: 每次增长 50%
- `--max-interval 10800`: 最大间隔 10800 秒（3 小时）

当检测到断网时，会自动报告超时时间范围，例如：**超时在 45~68 分钟之间**

**其他检测模式**:

| 模式 | 用途 | 适用场景 |
|------|------|----------|
| `--mode ladder` | 梯级增长探测超时 | 首次使用，自动测定超时时间 |
| `--mode silent --interval 2100` | 静默模式测试固定间隔 | 验证特定间隔是否会超时 |
| `--mode active --interval 60` | 主动模式持续检测 | 持续监控网络状态 |

静默模式示例：
```powershell
# 每隔 35 分钟（2100 秒）只做 2 次检测，中间零请求
python src/monitor.py --mode silent --interval 2100
```

#### Phase 2: 配置保活程序

1. 复制 `config.example.yaml` 为 `config.yaml`，或直接运行主程序自动生成配置：
```powershell
python src/keepalive.py --create-config
```

2. 填写你的校园网登录信息：
```yaml
portal:
  login_url: "http://10.0.0.1/eportal/index.jsp"
  username: "your_student_id"
  password: "your_password"
```

3. 根据 Phase 1 的结果设置心跳间隔，建议设为超时时间的 1/3：
```yaml
keepalive:
  interval_seconds: 600  # 超时 30 分钟 -> 间隔 600 秒（10 分钟）
```

#### Phase 3: 运行

**使用 Python 运行**：
```powershell
python src/keepalive.py
```

**或使用打包好的 EXE**：
```powershell
.\KeepAlive.exe
```

**命令行参数**：
```powershell
python src/keepalive.py --help
python src/keepalive.py --no-tray        # 不显示托盘图标
python src/keepalive.py --interval 300   # 设置心跳间隔为 300 秒
python src/keepalive.py --check          # 只检测一次网络状态
python src/keepalive.py --login          # 只执行一次登录操作
```

### Android 版本

<span style="color: orange; font-weight: bold;">🚧 开发中 · 即将推出</span>

Android 版本正在开发中，将提供与 Windows 版本相同的核心功能：

- 网络保活与自动重登录
- 后台服务运行
- 桌面通知提醒
- 图形化配置界面

预计将在后续版本发布。如果您有特定需求或希望参与测试，欢迎在 Issues 中提出。

---

## 配置说明

### 完整配置示例

`config.yaml` 配置文件包含以下部分：

```yaml
portal:
  # 校园网登录页 URL（必填）
  # 通常形如 http://10.x.x.x/eportal/ 或 http://portal.xxx.edu.cn/
  login_url: "http://10.0.0.1/eportal/index.jsp"

  # 你的校园网账号（通常是学号）
  username: "your_student_id"

  # 你的密码（首次运行后会自动加密保存）
  password: "your_password"

  # 如果登录页需要额外的表单字段，在这里添加
  extra_fields:
    # service: ""
    # queryString: ""

keepalive:
  # 心跳间隔（秒）
  # 建议设置为校园网超时时间的 1/3
  # 例如：超时 30 分钟 -> 间隔 600 秒（10 分钟）
  interval_seconds: 600

  # 心跳检测目标 URL
  targets:
    - "http://www.baidu.com"
    - "http://connect.rom.miui.com/generate_204"

auto_login:
  # 是否启用自动重新登录
  enabled: true

  # 登录失败时最大重试次数
  max_retries: 3

  # 重试间隔（秒）
  retry_delay_seconds: 5

logging:
  # 日志级别: DEBUG, INFO, WARNING, ERROR
  level: "INFO"

  # 单个日志文件最大大小（MB）
  max_size_mb: 5

  # 保留的历史日志文件数量
  backup_count: 3
```

### 配置说明

| 配置项 | 说明 | 推荐值 |
|--------|------|--------|
| `portal.login_url` | 校园网登录页面 URL | 需自行获取 |
| `portal.username` | 学号/用户名 | 必填 |
| `portal.password` | 校园网密码 | 必填 |
| `keepalive.interval_seconds` | 心跳间隔（秒） | 超时时间的 1/3 |
| `auto_login.enabled` | 是否启用自动登录 | true |
| `auto_login.max_retries` | 登录失败重试次数 | 3 |
| `logging.level` | 日志级别 | INFO |

---

## 常见问题

### 超时检测相关

**Q: 为什么需要先检测超时时间？**

A: 不同学校的校园网系统超时策略不同，有的 20 分钟，有的 1 小时以上。如果心跳间隔设置过短会产生不必要的网络请求，设置过长则可能被断网。通过超时检测可以找到最合适的间隔。

**Q: 梯级模式和静默模式有什么区别？**

A:
- **梯级模式**: 从短到长逐步测试，自动找到超时临界值，适合首次使用
- **静默模式**: 手动指定间隔进行测试，用于验证特定间隔是否安全

**Q: 检测过程中需要做什么？**

A: 不需要做任何操作。脚本会自动运行，直到检测到断网或达到最大间隔。检测完成后会在终端显示结果。

### 自动登录相关

**Q: 自动登录失败怎么办？**

A: 可能的原因和解决方法：

1. **登录 URL 错误**: 检查 `portal.login_url` 是否正确，建议在浏览器中访问确认
2. **凭据错误**: 检查 `username` 和 `password` 是否正确
3. **需要额外字段**: 部分校园网登录需要额外表单字段（如服务选择、运营商等），可在 `extra_fields` 中配置
4. **网络问题**: 确保电脑已连接校园网但未登录

**Q: 如何获取登录 URL？**

A:
1. 在浏览器中打开任意网页，会被重定向到校园网登录页
2. 复制浏览器地址栏中的 URL（通常形如 `http://10.x.x.x/eportal/...`）
3. 粘贴到配置文件中的 `login_url` 字段

**Q: 密码会安全存储吗？**

A: 是的。密码使用 AES 加密算法加密后存储在本地配置文件中，加密密钥保存在 `.key` 文件中。即使配置文件被复制到其他设备，也无法解密密码。

### 运行相关

**Q: 托盘图标消失了怎么办？**

A:
1. 检查程序是否仍在运行（任务管理器中查看进程）
2. 如果程序崩溃，查看日志文件 `logs/keepalive.log` 了解错误原因
3. 可以使用 `--no-tray` 参数启动，然后在终端中查看日志

**Q: 如何查看运行日志？**

A:
1. 右键点击托盘图标 → "查看日志"
2. 或直接打开 `logs/` 目录查看日志文件
3. 日志按天轮转，保留最近 3 天的日志

**Q: 程序运行时能否修改配置？**

A: 可以。右键点击托盘图标 → "配置"，在图形界面中修改配置并保存，程序会自动重新加载配置。修改配置时心跳会暂时暂停。

### 其他问题

**Q: 工具会产生多少网络流量？**

A: 心跳请求非常轻量，通常只有几百字节。以 10 分钟间隔为例，每小时约 6 次，每天约 144 次，总流量不足 100KB。

**Q: 使用此工具是否违反学校规定？**

A: 本工具仅用于个人学习和便利，定时发送常规 HTTP 请求不会对校园网造成负担。建议遵守学校网络使用规定，合理使用。

**Q: 支持哪些校园网系统？**

A: 工具支持大多数基于 Web Portal 认证的校园网系统。自动登录模块支持多种登录表单类型，并会自动分析登录页面结构。如果遇到不支持的系统，欢迎在 Issues 中反馈。

---

## 技术架构

### 技术栈

- **语言**: Python 3.8+
- **GUI 框架**: Tkinter（Windows 版本）
- **HTTP 请求**: requests
- **加密**: cryptography (Fernet)
- **配置管理**: PyYAML
- **系统通知**: Windows Toast (win10toast)

### 核心模块

```
src/
├── keepalive.py          # 主程序入口，服务编排
├── heartbeat.py          # 心跳服务，定时发送请求
├── network_checker.py    # 网络状态检测
├── auto_login.py         # 自动登录模块
├── monitor.py            # 超时检测脚本
├── config_manager.py     # 配置管理与加密
├── tray_icon.py          # 系统托盘图标
├── notifier.py           # Windows 通知
├── config_gui.py         # 图形配置界面
└── logger_setup.py       # 日志系统设置
```

### 工作流程

1. **初始化阶段**
   - 加载配置文件
   - 初始化加密器
   - 分析登录页面结构

2. **心跳阶段**
   - 按配置间隔发送 HTTP 请求
   - 检测网络状态（在线/离线）
   - 更新托盘图标状态

3. **断网处理**
   - 检测到断网后发送通知
   - 自动执行登录流程
   - 失败时重试（可配置次数）

4. **登录流程**
   - 发送预请求获取 Cookie
   - 分析登录表单结构
   - 提交登录凭据
   - 处理多因素认证（如需要）

### 目录结构

```
keep online/
├── src/                    # 源代码
│   ├── keepalive.py       # 主程序
│   ├── heartbeat.py       # 心跳服务
│   ├── auto_login.py      # 自动登录
│   ├── network_checker.py # 网络检测
│   ├── monitor.py         # 超时检测
│   ├── config_manager.py  # 配置管理
│   ├── tray_icon.py       # 托盘图标
│   ├── notifier.py        # 通知模块
│   ├── config_gui.py      # 配置界面
│   └── logger_setup.py    # 日志设置
├── logs/                   # 日志目录
├── config.yaml             # 用户配置（需自行创建）
├── config.example.yaml     # 配置示例
├── requirements.txt        # Python 依赖
└── README.md              # 本文档
```

---

## 开发与贡献

欢迎贡献代码、报告 Bug 或提出建议。

### 开发环境设置

```powershell
git clone <repository>
cd "keep online"
pip install -r requirements.txt
python src/keepalive.py
```

### 代码规范

- 遵循 PEP 8 代码风格
- 添加类型提示
- 编写清晰的注释和文档字符串

---

## 许可证

MIT License - 详见 LICENSE 文件

---

## 致谢

- 本工具参考了多个校园网保活项目的实现思路
- 感谢所有贡献者和测试用户

---

<div align="center">

如有问题或建议，欢迎提交 [Issues](../../issues)

</div>
