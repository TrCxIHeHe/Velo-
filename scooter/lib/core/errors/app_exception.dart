sealed class AppException implements Exception {
  const AppException(this.message);
  final String message;

  @override
  String toString() => message;
}

final class NetworkException extends AppException {
  const NetworkException([super.message = 'Network error. Please try again.']);
}

final class UnauthorizedException extends AppException {
  const UnauthorizedException(
      [super.message = 'Session expired. Please log in again.']);
}

final class ApiException extends AppException {
  const ApiException({required this.code, required String message})
      : super(message);
  final String code;
}