abstract final class ApiConstants {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  // Auth — Phase 1 frozen contract
  static const String login = '/auth/login';
  static const String refresh = '/auth/refresh';
  static const String logout = '/auth/logout';
  static const String me = '/auth/me';

  // Wallet — Track B Phase 1
  static const String wallet = '/wallet';
  static const String walletTransactions = '/wallet/transactions';

  // Ride — Track A Phase 2/3
  static const String rideBase = '/ride';
  static const String rideRequest = '/ride/request';
  static const String rideToken = '/ride/token';

  // Docks — Track B Phase 3
  static const String docks = '/docks';

  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration receiveTimeout = Duration(seconds: 10);
}
