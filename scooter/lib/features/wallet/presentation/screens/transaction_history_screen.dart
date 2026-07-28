import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/core/widgets/transaction_tile.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/presentation/providers/transaction_history_providers.dart';

class TransactionHistoryScreen extends ConsumerStatefulWidget {
  const TransactionHistoryScreen({super.key});

  @override
  ConsumerState<TransactionHistoryScreen> createState() => _TransactionHistoryScreenState();
}

class _TransactionHistoryScreenState extends ConsumerState<TransactionHistoryScreen> {
  final _scrollCtrl = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollCtrl.removeListener(_onScroll);
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 200) {
      ref.read(transactionHistoryProvider.notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(transactionHistoryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Transactions')),
      body: Builder(builder: (context) {
        if (state.isLoadingFirstPage) return const StateView.loading();
        if (state.error != null && state.items.isEmpty) {
          return StateView.error(
            subtitle: state.error!,
            onRetry: () => ref.read(transactionHistoryProvider.notifier).loadFirstPage(),
          );
        }
        if (state.items.isEmpty) {
          return const StateView.empty(subtitle: 'No transactions yet');
        }

        final grouped = _groupByDate(state.items);

        return RefreshIndicator(
          onRefresh: () => ref.read(transactionHistoryProvider.notifier).loadFirstPage(),
          child: ListView.builder(
            controller: _scrollCtrl,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            itemCount: grouped.length + (state.isLoadingMore ? 1 : 0),
            itemBuilder: (context, index) {
              if (index >= grouped.length) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                );
              }
              final group = grouped[index];
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 16, bottom: 4),
                    child: Text(
                      group.label,
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(color: Theme.of(context).hintColor),
                    ),
                  ),
                  ...group.items.map((t) => TransactionTile(transaction: t)),
                ],
              );
            },
          ),
        );
      }),
    );
  }

  List<_TransactionGroup> _groupByDate(List<WalletTransaction> items) {
    final formatter = DateFormat('d MMM yyyy');
    final groups = <String, List<WalletTransaction>>{};
    for (final item in items) {
      final label = formatter.format(item.createdAt.toLocal());
      groups.putIfAbsent(label, () => []).add(item);
    }
    return groups.entries.map((e) => _TransactionGroup(e.key, e.value)).toList();
  }
}

class _TransactionGroup {
  const _TransactionGroup(this.label, this.items);
  final String label;
  final List<WalletTransaction> items;
}
