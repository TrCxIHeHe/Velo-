import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

abstract interface class WalletRepository {
  Future<Wallet> getWallet();
  Future<List<WalletTransaction>> getTransactions({int limit = 50, int offset = 0});
}
