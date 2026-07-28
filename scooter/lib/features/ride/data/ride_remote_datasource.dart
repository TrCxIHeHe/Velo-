import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';

class RideRemoteDataSource {
  const RideRemoteDataSource(this._dio);

  final Dio _dio;

  Future<Ride> getRide(String id) async {
    try {
      final r = await _dio.get('${ApiConstants.rides}/$id');
      return Ride.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<Ride?> getActiveRide() async {
    try {
      final r = await _dio.get('${ApiConstants.rides}/active');
      final data = r.data['data'];
      if (data == null) return null;
      return Ride.fromJson(data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<RideToken> requestToken(String dockId) async {
    try {
      final r = await _dio.post(
        '${ApiConstants.rides}/token',
        data: {'dock_id': dockId},
      );
      return RideToken.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<Ride> endRide(String rideId, String dockId) async {
    try {
      final r = await _dio.post(
        '${ApiConstants.rides}/$rideId/end',
        data: {'dock_id': dockId},
      );
      return Ride.fromJson(r.data['data'] as Map<String, dynamic>);
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
