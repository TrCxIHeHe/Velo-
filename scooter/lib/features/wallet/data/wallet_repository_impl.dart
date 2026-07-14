import 'package:scooter/features/wallet/data/wallet_remote_datasource.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';

class WalletRepositoryImpl implements WalletRepository {
  const WalletRepositoryImpl(this._ds);

  final WalletRemoteDataSource _ds;

  @override
  Future<Wallet> getWallet() => _ds.getWallet();

  @override
  Future<List<WalletTransaction>> getTransactions({
    int limit = 50,
    int offset = 0,
  }) => _ds.getTransactions(limit: limit, offset: offset);
}
