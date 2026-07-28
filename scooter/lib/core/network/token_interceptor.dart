import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/storage/secure_storage.dart';

class TokenInterceptor extends Interceptor {
  TokenInterceptor({
    required this.storage,
    required this.dio,
    required this.onSessionExpired,
  });

  final SecureStorageService storage;
  final Dio dio;
  final void Function() onSessionExpired;
  bool _isRefreshing = false;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await storage.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    // Binds refresh tokens to this install (see backend AuthService.refresh)
    // — sent on every request, including /auth/login and /auth/refresh
    // since those also go through this dio instance.
    options.headers['X-Device-Id'] = await storage.getOrCreateDeviceId();
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final is401 = err.response?.statusCode == 401;
    final isRefresh = err.requestOptions.path.contains(ApiConstants.refresh);

    if (is401 && !isRefresh && !_isRefreshing) {
      _isRefreshing = true;
      try {
        final refreshed = await _attemptRefresh();
        if (refreshed) {
          final token = await storage.getAccessToken();
          final opts = err.requestOptions;
          opts.headers['Authorization'] = 'Bearer $token';
          final response = await dio.fetch(opts);
          handler.resolve(response);
          return;
        }
      } catch (_) {
      } finally {
        _isRefreshing = false;
      }
      await storage.clearSession();
      onSessionExpired();
    }
    handler.next(err);
  }

  Future<bool> _attemptRefresh() async {
    final refreshToken = await storage.getRefreshToken();
    if (refreshToken == null) return false;
    try {
      final response = await dio.post(
        ApiConstants.refresh,
        data: {'refresh_token': refreshToken},
      );
      final data = response.data['data'] as Map<String, dynamic>;
      await storage.saveSession(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return true;
    } on DioException {
      return false;
    }
  }
}