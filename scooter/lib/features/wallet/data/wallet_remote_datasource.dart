import 'package:dio/dio.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/wallet/domain/models/razorpay_order.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

class WalletRemoteDataSource {
  const WalletRemoteDataSource(this._dio);

  final Dio _dio;

  Future<Wallet> getBalance() async {
    try {
      final r = await _dio.get(ApiConstants.wallet);
      return Wallet.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<TransactionPage> listTransactions({int skip = 0, int limit = 20}) async {
    try {
      final r = await _dio.get(
        ApiConstants.walletTransactions,
        queryParameters: {'skip': skip, 'limit': limit},
      );
      return TransactionPage.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<Wallet> topUp(double amount, {String? referenceId}) async {
    try {
      final r = await _dio.post(
        ApiConstants.walletTopup,
        data: {
          'amount': amount,
          if (referenceId != null) 'reference_id': referenceId,
        },
      );
      return Wallet.fromJson(r.data['data'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  Future<RazorpayOrder> createRazorpayOrder(double amount) async {
    try {
      final r = await _dio.post(
        ApiConstants.paymentsOrders,
        data: {'amount': amount},
      );
      return RazorpayOrder.fromJson(r.data['data'] as Map<String, dynamic>);
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
