import 'package:scooter/features/wallet/data/wallet_remote_datasource.dart';
import 'package:scooter/features/wallet/domain/models/razorpay_order.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';

class WalletRepositoryImpl implements WalletRepository {
  const WalletRepositoryImpl(this._remote);

  final WalletRemoteDataSource _remote;

  @override
  Future<Wallet> getBalance() => _remote.getBalance();

  @override
  Future<TransactionPage> listTransactions({int skip = 0, int limit = 20}) =>
      _remote.listTransactions(skip: skip, limit: limit);

  @override
  Future<Wallet> topUp(double amount, {String? referenceId}) =>
      _remote.topUp(amount, referenceId: referenceId);

  @override
  Future<RazorpayOrder> createRazorpayOrder(double amount) =>
      _remote.createRazorpayOrder(amount);
}
