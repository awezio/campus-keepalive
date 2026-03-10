/// Application configuration data class
class AppConfig {
  final String loginUrl;
  final String username;
  final String password;
  final int heartbeatInterval;
  final bool autoLoginEnabled;

  const AppConfig({
    required this.loginUrl,
    required this.username,
    required this.password,
    required this.heartbeatInterval,
    this.autoLoginEnabled = true,
  });

  /// Create AppConfig from JSON
  factory AppConfig.fromJson(Map<String, dynamic> json) {
    return AppConfig(
      loginUrl: json['login_url'] as String? ?? '',
      username: json['username'] as String? ?? '',
      password: json['password'] as String? ?? '',
      heartbeatInterval: json['heartbeat_interval'] as int? ?? 600,
      autoLoginEnabled: json['auto_login_enabled'] as bool? ?? true,
    );
  }

  /// Convert AppConfig to JSON
  Map<String, dynamic> toJson() {
    return {
      'login_url': loginUrl,
      'username': username,
      'password': password,
      'heartbeat_interval': heartbeatInterval,
      'auto_login_enabled': autoLoginEnabled,
    };
  }

  @override
  String toString() {
    return 'AppConfig(loginUrl: $loginUrl, username: $username, interval: $heartbeatInterval)';
  }

  /// Default configuration
  static const AppConfig empty = AppConfig(
    loginUrl: '',
    username: '',
    password: '',
    heartbeatInterval: 600,
    autoLoginEnabled: false,
  );
}
