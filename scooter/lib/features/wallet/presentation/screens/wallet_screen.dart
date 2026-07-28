import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/balance_card.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/core/widgets/transaction_tile.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_state.dart';
import 'package:scooter/router/app_router.dart';

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(walletNotifierProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Wallet'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(walletNotifierProvider.notifier).refresh(),
          ),
        ],
      ),
      body: switch (state) {
        WalletInitial() || WalletLoading() => const StateView.loading(),
        WalletError(:final message) => StateView.error(
            subtitle: message,
            onRetry: () => ref.read(walletNotifierProvider.notifier).load(),
          ),
        WalletLoaded(:final wallet, :final recentTransactions) => RefreshIndicator(
            onRefresh: () => ref.read(walletNotifierProvider.notifier).refresh(),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                BalanceCard(balance: wallet.balance, currency: wallet.currency),
                const SizedBox(height: 16),
                PrimaryButton(
                  label: 'Add Money',
                  icon: Icons.add,
                  onPressed: () => context.pushNamed(AppRoutes.recharge),
                ),
                const SizedBox(height: 28),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Transactions',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Theme.of(context).hintColor,
                          ),
                    ),
                    TextButton(
                      onPressed: () => context.pushNamed(AppRoutes.transactionHistory),
                      child: const Text('View all'),
                    ),
                  ],
                ),
                if (recentTransactions.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: StateView.empty(subtitle: 'No transactions yet'),
                  )
                else
                  ...recentTransactions.map((t) => TransactionTile(transaction: t)),
              ],
            ),
          ),
      },
    );
  }
}
