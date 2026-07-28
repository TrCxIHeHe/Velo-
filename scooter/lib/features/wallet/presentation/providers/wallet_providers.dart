import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/wallet/data/wallet_remote_datasource.dart';
import 'package:scooter/features/wallet/data/wallet_repository_impl.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_state.dart';

const int kRecentTransactionsCount = 5;

final Provider<WalletRemoteDataSource> walletDataSourceProvider =
    Provider<WalletRemoteDataSource>(
  (ref) => WalletRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<WalletRepository> walletRepositoryProvider = Provider<WalletRepository>(
  (ref) => WalletRepositoryImpl(ref.watch(walletDataSourceProvider)),
);

class WalletNotifier extends StateNotifier<WalletState> {
  WalletNotifier(this._repo) : super(const WalletInitial()) {
    load();
  }

  final WalletRepository _repo;

  Future<void> load() async {
    state = const WalletLoading();
    await refresh();
  }

  Future<void> refresh() async {
    try {
      final wallet = await _repo.getBalance();
      final txPage = await _repo.listTransactions(limit: kRecentTransactionsCount);
      state = WalletLoaded(wallet, txPage.items);
    } catch (e) {
      state = WalletError(e.toString());
    }
  }
}

final StateNotifierProvider<WalletNotifier, WalletState> walletNotifierProvider =
    StateNotifierProvider<WalletNotifier, WalletState>(
  (ref) => WalletNotifier(ref.watch(walletRepositoryProvider)),
);
