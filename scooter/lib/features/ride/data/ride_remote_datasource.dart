import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';

class RideRemoteDataSource {
  const RideRemoteDataSource(this._dio);

  final Dio _dio;

  /// POST /api/v1/ride/request
  /// 201 on success. 409 if ride already active (RIDE_ALREADY_ACTIVE).
  Future<void> requestRide() async {
    try {
      await _dio.post(ApiConstants.rideRequest);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  /// POST /api/v1/ride/token
  /// Returns RideTokenResponse: { ride_token, expires_in, expires_at }
  Future<RideToken> issueToken() async {
    try {
      final r = await _dio.post(ApiConstants.rideToken);
      return RideToken.fromJson(r.data['data'] as Map<String, dynamic>);
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
