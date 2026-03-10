/// Network status enumeration
enum NetworkStatus {
  /// Device is offline, no network connection
  offline,

  /// Device is online but not authenticated (captive portal detected)
  portal,

  /// Device is online and authenticated
  online,

  /// Network status is unknown or checking
  unknown,
}
