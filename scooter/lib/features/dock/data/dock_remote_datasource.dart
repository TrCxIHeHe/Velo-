import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

class DockRemoteDataSource {
  const DockRemoteDataSource(this._dio);

  final Dio _dio;

  Future<List<Dock>> listDocks() async {
    try {
      final r = await _dio.get(ApiConstants.docks);
      return (r.data['data'] as List)
          .map((e) => Dock.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _map(e);
    }
  }

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
