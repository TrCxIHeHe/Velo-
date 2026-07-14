import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

class DockRemoteDataSource {
  const DockRemoteDataSource(this._dio);

  final Dio _dio;

  /// GET /api/v1/docks?limit=&offset=
  /// Returns list<DockResponse> — no available_slots field.
  Future<List<Dock>> listDocks({int limit = 50, int offset = 0}) async {
    try {
      final r = await _dio.get(
        ApiConstants.docks,
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final list = r.data['data'] as List<dynamic>;
      return list
          .map((e) => Dock.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  /// GET /api/v1/docks/{dock_id}
  /// Returns DockWithSlotsResponse — includes available_slots.
  Future<Dock> getDock(String dockId) async {
    try {
      final r = await _dio.get('${ApiConstants.docks}/$dockId');
      return Dock.fromJson(r.data['data'] as Map<String, dynamic>);
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
