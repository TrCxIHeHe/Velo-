import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';

const int kPageSize = 20;

class TransactionHistoryState {
  const TransactionHistoryState({
    this.items = const [],
    this.total = 0,
    this.isLoadingFirstPage = true,
    this.isLoadingMore = false,
    this.error,
  });

  final List<WalletTransaction> items;
  final int total;
  final bool isLoadingFirstPage;
  final bool isLoadingMore;
  final String? error;

  bool get hasMore => items.length < total;

  TransactionHistoryState copyWith({
    List<WalletTransaction>? items,
    int? total,
    bool? isLoadingFirstPage,
    bool? isLoadingMore,
    String? error,
    bool clearError = false,
  }) {
    return TransactionHistoryState(
      items: items ?? this.items,
      total: total ?? this.total,
      isLoadingFirstPage: isLoadingFirstPage ?? this.isLoadingFirstPage,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class TransactionHistoryNotifier extends StateNotifier<TransactionHistoryState> {
  TransactionHistoryNotifier(this._repo) : super(const TransactionHistoryState()) {
    loadFirstPage();
  }

  final WalletRepository _repo;

  Future<void> loadFirstPage() async {
    state = state.copyWith(isLoadingFirstPage: true, clearError: true);
    try {
      final page = await _repo.listTransactions(skip: 0, limit: kPageSize);
      state = state.copyWith(
        items: page.items,
        total: page.total,
        isLoadingFirstPage: false,
      );
    } catch (e) {
      state = state.copyWith(isLoadingFirstPage: false, error: e.toString());
    }
  }

  Future<void> loadMore() async {
    if (state.isLoadingMore || !state.hasMore) return;
    state = state.copyWith(isLoadingMore: true, clearError: true);
    try {
      final page = await _repo.listTransactions(skip: state.items.length, limit: kPageSize);
      state = state.copyWith(
        items: [...state.items, ...page.items],
        total: page.total,
        isLoadingMore: false,
      );
    } catch (e) {
      state = state.copyWith(isLoadingMore: false, error: e.toString());
    }
  }
}

final StateNotifierProvider<TransactionHistoryNotifier, TransactionHistoryState>
    transactionHistoryProvider =
    StateNotifierProvider<TransactionHistoryNotifier, TransactionHistoryState>(
  (ref) => TransactionHistoryNotifier(ref.watch(walletRepositoryProvider)),
);
