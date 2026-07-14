import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';

class RideRemoteDataSource {
  const RideRemoteDataSource(this._dio);

  final Dio _dio;

  /// POST /api/v1/ride/request
  /// 201 with full RideResponse. 409 if already active (RIDE_ALREADY_ACTIVE).
  Future<Ride> requestRide() async {
    try {
      final r = await _dio.post(ApiConstants.rideRequest);
      return Ride.fromJson(r.data['data'] as Map<String, dynamic>);
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

  /// GET /api/v1/ride/{ride_id} — full ride record.
  Future<Ride> getRide(String rideId) async {
    try {
      final r = await _dio.get('${ApiConstants.rideBase}/$rideId');
      return Ride.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  /// GET /api/v1/ride/status/{ride_id} — cheap poll, id + status only.
  Future<String> getRideStatus(String rideId) async {
    try {
      final r = await _dio.get('${ApiConstants.rideBase}/status/$rideId');
      return (r.data['data'] as Map<String, dynamic>)['status'] as String;
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
