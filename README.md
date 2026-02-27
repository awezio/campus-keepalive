# Campus Network Keep-Alive 校园网保活工具

一个 Windows 下的校园网保活程序，防止校园网 Web Portal 认证网关因长时间无网络活动而自动断开连接。

## 功能特性

- **网络保活**: 定时发送轻量级 HTTP 请求，防止网关超时断开
- **自动重登录**: 检测到断网后自动使用保存的凭据重新登录
- **系统托盘**: 后台运行，托盘图标显示状态
- **Windows 通知**: 断网/重连时弹出 Toast 通知
- **日志记录**: 完整的运行日志，方便排查问题

## 使用步骤

### Phase 1: 检测超时时间

首次使用前，需要先运行监控脚本确定校园网「无活动多久会断网」。有两种模式：

| 模式 | 含义 | 适用场景 |
|------|------|----------|
| **梯级模式** `--mode ladder` | **推荐**：从短间隔开始逐步增长，自动探测超时临界值 | 高效精确测定超时时间 |
| **静默模式** `--mode silent` | 每个周期只在开始、结束各检测 1 次，**中间整段时间不发任何请求** | 测定固定间隔是否超时 |
| **主动模式** `--mode active`（默认） | 每隔 interval 秒发一次请求做检测 | 会持续产生流量，无法测出超时 |
**推荐：用梯级模式自动探测超时**

```powershell
cd "D:\keep online"
pip install -r requirements.txt
# 梯级模式：从 30 分钟开始，自动增长直到断网
python src/monitor.py --mode ladder
```

- `--start-interval 1800`（默认）初始间隔 1800 秒（30 分钟）
- `--multiplier 1.5`（默认）每次增长 50%
- `--max-interval 10800`（默认）最大间隔 10800 秒（3 小时）
- 当检测到断网时，会自动报告超时时间范围（例如：超时在 45~68 分钟之间）

**或使用静默模式手动测试**：

```powershell
# 静默模式：每 35 分钟只做 2 次检测，中间零请求
python src/monitor.py --mode silent --interval 2100
```

### Phase 2: 配置保活程序

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 填写你的校园网登录信息
3. 根据 Phase 1 的结果设置心跳间隔

### Phase 3: 运行

```powershell
python src/keepalive.py
```

或使用打包好的 EXE：
```powershell
.\KeepAlive.exe
```

## 配置说明

`config.yaml` 示例：

```yaml
portal:
  login_url: "http://10.x.x.x/login"
  username: "your_student_id"
  password: "your_password"  # 首次运行后会自动加密

keepalive:
  interval_seconds: 600  # 心跳间隔，建议设为超时时间的 1/3
  
auto_login:
  enabled: true
  max_retries: 3
```

## 目录结构

```
keep online/
├── src/
│   ├── monitor.py          # Phase 1: 超时检测脚本
│   ├── keepalive.py        # Phase 2: 主程序
│   ├── network_checker.py  # 网络状态检测
│   ├── auto_login.py       # 自动登录
│   └── ...
├── logs/                   # 日志目录
├── config.yaml             # 用户配置
└── requirements.txt        # Python 依赖
```

## 注意事项

- 本工具仅用于个人学习和便利，请遵守学校网络使用规定
- 密码会使用 AES 加密存储在本地配置文件中
- 建议将心跳间隔设为检测到的超时时间的 1/3

## License

MIT License
