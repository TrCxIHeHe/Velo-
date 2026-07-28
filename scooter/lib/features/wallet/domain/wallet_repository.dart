import 'package:scooter/features/wallet/domain/models/razorpay_order.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

abstract interface class WalletRepository {
  Future<Wallet> getBalance();

  Future<TransactionPage> listTransactions({int skip = 0, int limit = 20});

  /// Dev/test direct credit — see backend README's "free money" warning.
  /// Kept as a fallback path; the primary flow is [createRazorpayOrder].
  Future<Wallet> topUp(double amount, {String? referenceId});

  Future<RazorpayOrder> createRazorpayOrder(double amount);
}
