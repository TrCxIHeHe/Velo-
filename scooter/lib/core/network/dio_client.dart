import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/network/token_interceptor.dart';
import 'package:scooter/core/storage/secure_storage.dart';

Dio createDio(SecureStorageService storage, void Function() onSessionExpired) {
  final dio = Dio(
    BaseOptions(
      baseUrl: ApiConstants.baseUrl,
      connectTimeout: ApiConstants.connectTimeout,
      receiveTimeout: ApiConstants.receiveTimeout,
      headers: {'Content-Type': 'application/json'},
    ),
  );
  dio.interceptors.add(
    TokenInterceptor(
      storage: storage,
      dio: dio,
      onSessionExpired: onSessionExpired,
    ),
  );
  return dio;
}