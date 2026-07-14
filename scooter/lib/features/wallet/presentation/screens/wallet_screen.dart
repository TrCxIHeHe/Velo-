import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_state.dart';

class WalletScreen extends ConsumerStatefulWidget {
  const WalletScreen({super.key});

  @override
  ConsumerState<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends ConsumerState<WalletScreen> {
  @override
  void initState() {
    super.initState();
    // Load on first mount. Using addPostFrameCallback to avoid calling
    // state changes during build — same pattern as SplashScreen's initState.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(walletNotifierProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(walletNotifierProvider);
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Wallet'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(walletNotifierProvider.notifier).refresh(),
          ),
        ],
      ),
      body: switch (state) {
        WalletInitial() || WalletLoading() => const Center(
            child: CircularProgressIndicator(),
          ),
        WalletError(:final message) => _ErrorBody(
            message: message,
            onRetry: () =>
                ref.read(walletNotifierProvider.notifier).refresh(),
          ),
        WalletLoaded(:final wallet, :final transactions) => RefreshIndicator(
            onRefresh: () =>
                ref.read(walletNotifierProvider.notifier).refresh(),
            child: CustomScrollView(
              slivers: [
                SliverToBoxAdapter(
                  child: _BalanceCard(
                    balance: wallet.balance,
                    currency: wallet.currency,
                  ),
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 24, 20, 8),
                    child: Text(
                      'Transactions',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ),
                ),
                if (transactions.isEmpty)
                  const SliverFillRemaining(
                    hasScrollBody: false,
                    child: _EmptyTransactions(),
                  )
                else
                  SliverList.separated(
                    itemCount: transactions.length,
                    separatorBuilder: (_, __) =>
                        const Divider(indent: 20, endIndent: 20, height: 1),
                    itemBuilder: (context, i) =>
                        _TransactionTile(transaction: transactions[i]),
                  ),
              ],
            ),
          ),
      },
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.balance, required this.currency});

  final double balance;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      decoration: BoxDecoration(
        color: colorScheme.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Balance',
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: colorScheme.onPrimary.withOpacity(0.7),
                ),
          ),
          const SizedBox(height: 8),
          Text(
            '${_currencySymbol(currency)}${balance.toStringAsFixed(2)}',
            style: Theme.of(context).textTheme.displaySmall?.copyWith(
                  color: colorScheme.onPrimary,
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            currency,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: colorScheme.onPrimary.withOpacity(0.6),
                ),
          ),
        ],
      ),
    );
  }

  String _currencySymbol(String currency) {
    return switch (currency.toUpperCase()) {
      'INR' => '₹',
      'USD' => '\$',
      'EUR' => '€',
      _ => '',
    };
  }
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({required this.transaction});

  final WalletTransaction transaction;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isCredit =
        transaction.type == 'CREDIT' || transaction.type == 'REFUND';

    final amountColor = isCredit ? Colors.green.shade700 : colorScheme.error;
    final amountPrefix = isCredit ? '+' : '−';
    final icon = switch (transaction.type) {
      'CREDIT' => Icons.arrow_downward_rounded,
      'REFUND' => Icons.undo_rounded,
      'DEBIT' => Icons.arrow_upward_rounded,
      _ => Icons.swap_horiz_rounded,
    };

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      leading: CircleAvatar(
        backgroundColor:
            isCredit ? Colors.green.shade50 : colorScheme.errorContainer,
        child: Icon(icon,
            color: isCredit ? Colors.green.shade700 : colorScheme.error,
            size: 18),
      ),
      title: Text(
        _typeLabel(transaction.type),
        style: Theme.of(context).textTheme.bodyMedium,
      ),
      subtitle: Text(
        _formatDate(transaction.createdAt),
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: colorScheme.outline,
            ),
      ),
      trailing: Text(
        '$amountPrefix₹${transaction.amount.toStringAsFixed(2)}',
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: amountColor,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }

  String _typeLabel(String type) => switch (type) {
        'CREDIT' => 'Wallet Recharge',
        'DEBIT' => 'Ride Fare',
        'REFUND' => 'Refund',
        _ => type,
      };

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.day} ${_month(local.month)} ${local.year}, '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }

  String _month(int m) => const [
        '',
        'Jan',
        'Feb',
        'Mar',
        'Apr',
        'May',
        'Jun',
        'Jul',
        'Aug',
        'Sep',
        'Oct',
        'Nov',
        'Dec'
      ][m];
}

class _EmptyTransactions extends StatelessWidget {
  const _EmptyTransactions();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.receipt_long_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.outlineVariant),
          const SizedBox(height: 16),
          Text(
            'No transactions yet',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.outline,
                ),
          ),
        ],
      ),
    );
  }
}

class _ErrorBody extends StatelessWidget {
  const _ErrorBody({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
              onPressed: onRetry,
            ),
          ],
        ),
      ),
    );
  }
}
