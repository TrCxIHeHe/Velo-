import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

class WalletRemoteDataSource {
  const WalletRemoteDataSource(this._dio);

  final Dio _dio;

  /// GET /api/v1/wallet
  /// Returns WalletResponse with computed balance field.
  Future<Wallet> getWallet() async {
    try {
      final r = await _dio.get(ApiConstants.wallet);
      return Wallet.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  /// GET /api/v1/wallet/transactions?limit=&offset=
  Future<List<WalletTransaction>> getTransactions({
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final r = await _dio.get(
        ApiConstants.walletTransactions,
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final list = r.data['data'] as List<dynamic>;
      return list
          .map((e) => WalletTransaction.fromJson(e as Map<String, dynamic>))
          .toList();
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
