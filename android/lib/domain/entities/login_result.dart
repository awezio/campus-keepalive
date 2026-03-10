/// Login result data class
class LoginResult {
  final bool success;
  final String message;
  final String? redirectUrl;
  final int responseCode;

  const LoginResult({
    required this.success,
    required this.message,
    this.redirectUrl,
    required this.responseCode,
  });

  /// Successful login result
  factory LoginResult.success({
    String? redirectUrl,
    int responseCode = 200,
  }) {
    return LoginResult(
      success: true,
      message: 'Login successful',
      redirectUrl: redirectUrl,
      responseCode: responseCode,
    );
  }

  /// Failed login result
  factory LoginResult.failure({
    required String message,
    int responseCode = 0,
  }) {
    return LoginResult(
      success: false,
      message: message,
      responseCode: responseCode,
    );
  }

  @override
  String toString() {
    return 'LoginResult(success: $success, message: $message, responseCode: $responseCode)';
  }
}
