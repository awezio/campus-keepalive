# Campus Keep-Alive - Android Application

<div align="center">

![Flutter](https://img.shields.io/badge/Flutter-3.19.6-blue?logo=flutter)
![Dart](https://img.shields.io/badge/Dart-3.3.3-blue?logo=dart)
![License](https://img.shields.io/badge/License-MIT-green)

Android版校园网保活工具，提供与Windows版本相同的核心功能。

[功能特性](#功能特性) • [项目结构](#项目结构) • [安装说明](#安装说明)

</div>

---

## 🚧 开发状态

<span style="color: orange; font-weight: bold; font-size: 1.2em;">🚧 开发中 · 即将推出</span>

Flutter应用正在积极开发中，将提供与Windows版本相同的核心功能：
- ✅ 网络保活与自动重登录
- ✅ 后台服务运行
- ✅ 图形化配置界面
- ✅ 本地通知提醒

---

## 功能特性

- **网络保活**: 定时发送轻量级HTTP请求保持网络活跃
- **自动重登录**: 检测到断网后自动重新登录校园网Portal
- **后台服务**: 使用WorkManager和Foreground Service确保持续运行
- **配置管理**: 图形化配置界面，安全存储凭据
- **本地通知**: 断网/重连时推送通知提醒
- **跨平台**: Flutter开发，未来可支持iOS等其他平台

---

## 技术架构

### 技术栈
- **Flutter 3.19.6**: 跨平台UI框架
- **Dart 3.3.3**: Flutter编程语言
- **Riverpod 2.4.9**: 状态管理
- **HTTP**: 网络请求库
- **connectivity_plus**: 网络连接检测
- **flutter_secure_storage**: 安全存储凭据
- **workmanager**: 后台任务调度
- **flutter_local_notifications**: 本地通知

### 项目结构
```
android/
├── lib/
│   ├── domain/              # 领域层
│   │   └── entities/       # 数据实体
│   │       ├── network_status.dart
│   │       ├── login_result.dart
│   │       └── app_config.dart
│   ├── data/                # 数据层
│   │   └── repositories/   # 数据仓库
│   │       ├── network_repository.dart
│   │       └── auth_repository.dart
│   ├── presentation/          # 表现层
│   │   └── pages/          # 页面
│   ├── models/               # 数据模型
│   └── main.dart             # 应用入口
├── pubspec.yaml            # 依赖配置
├── analysis_options.yaml    # 代码分析规则
└── README.md              # 项目说明
```

### 工作流程
1. **初始化**: 检测网络连接状态
2. **配置**: 从安全存储加载用户配置
3. **心跳**: 定期发送HTTP请求保持网络活跃
4. **检测**: 检测网络断开或Portal重定向
5. **登录**: 自动使用保存的凭据登录Portal
6. **通知**: 通知用户网络状态变化

---

## 安装说明

### 前置要求
- Flutter SDK 3.19.6或更高版本
- Dart SDK 3.3.3或更高版本
- Android Studio或VS Code（推荐）
- Git（版本控制）

### 安装Flutter SDK

#### Windows
```powershell
# 方法1: 使用官方安装包
# 访问 https://docs.flutter.dev/get-started/install/windows
# 下载flutter_windows_xxx.zip
# 解压到 C:\src\flutter
# 添加到PATH环境变量

# 方法2: 使用Chocolatey
choco install flutter

# 验证安装
flutter doctor
```

#### macOS
```bash
# 方法1: 使用Homebrew
brew install --cask flutter

# 方法2: 使用官方安装包
# 访问 https://docs.flutter.dev/get-started/install/macos

# 验证安装
flutter doctor
```

#### Linux
```bash
# 下载并解压
git clone https://github.com/flutter/flutter.git -b stable
export PATH="$PATH:`pwd`/flutter/bin:$PATH"

# 验证安装
flutter doctor
```

### 安装依赖

```bash
cd android
flutter pub get
```

### 运行应用

```bash
# 调试模式（开发）
flutter run

# Release模式
flutter run --release

# 构建APK
flutter build apk --release
```

---

## 开发指南

### 启动开发服务器
```bash
cd android
flutter run
```

### 运行测试
```bash
flutter test
```

### 代码格式化
```bash
flutter format .
```

### 代码分析
```bash
flutter analyze
```

---

## 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 许可证

本项目采用MIT许可证 - 详见 [LICENSE](../LICENSE) 文件

---

## 致谢

- Flutter团队提供优秀的跨平台框架
- Windows版本开发者提供参考实现
- 所有贡献者

---

**提示**: 这是Android版本的README。主项目README请查看 [项目根目录](../README.md)。
