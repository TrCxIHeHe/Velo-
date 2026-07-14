import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/wallet/data/wallet_remote_datasource.dart';
import 'package:scooter/features/wallet/data/wallet_repository_impl.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_state.dart';

final Provider<WalletRemoteDataSource> walletDataSourceProvider =
    Provider<WalletRemoteDataSource>(
  (ref) => WalletRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<WalletRepository> walletRepositoryProvider =
    Provider<WalletRepository>(
  (ref) => WalletRepositoryImpl(ref.watch(walletDataSourceProvider)),
);

class WalletNotifier extends StateNotifier<WalletState> {
  WalletNotifier(this._repo) : super(const WalletInitial());

  final WalletRepository _repo;

  Future<void> load() async {
    state = const WalletLoading();
    try {
      // Run both requests in parallel. wallet.balance is computed server-side
      // from ledger; transactions is the ledger itself.
      final walletFuture = _repo.getWallet();
      final txnFuture = _repo.getTransactions();
      final wallet = await walletFuture;
      final transactions = await txnFuture;
      state = WalletLoaded(wallet: wallet, transactions: transactions);
    } catch (e) {
      state = WalletError(e.toString());
    }
  }

  Future<void> refresh() => load();
}

final StateNotifierProvider<WalletNotifier, WalletState> walletNotifierProvider =
    StateNotifierProvider<WalletNotifier, WalletState>(
  (ref) => WalletNotifier(ref.watch(walletRepositoryProvider)),
);
