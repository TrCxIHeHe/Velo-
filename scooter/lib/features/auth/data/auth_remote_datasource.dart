import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/auth/domain/models/session.dart';
import 'package:scooter/features/auth/domain/models/user.dart';

class AuthRemoteDataSource {
  const AuthRemoteDataSource(this._dio);

  final Dio _dio;

  Future<Session> login(String firebaseIdToken) async {
    try {
      final r = await _dio.post(
        ApiConstants.login,
        data: {'firebase_id_token': firebaseIdToken},
      );
      return Session.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<void> logout(String refreshToken) async {
    try {
      await _dio.post(ApiConstants.logout,
          data: {'refresh_token': refreshToken});
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<User> getMe() async {
    try {
      final r = await _dio.get(ApiConstants.me);
      return User.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<User> updateName(String name) async {
    try {
      final r =
          await _dio.patch(ApiConstants.me, data: {'name': name});
      return User.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  AppException _map(DioException e) {
    if (e.response != null) {
      if (e.response!.statusCode == 401) return const UnauthorizedException();
      try {
        final err = e.response!.data['error'] as Map<String, dynamic>;
        return ApiException(
          code: err['code'] as String,
          message: err['message'] as String,
        );
      } catch (_) {}
    }
    return const NetworkException();
  }
}