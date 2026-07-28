import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

/// Transaction Tile (Figma `3:67` / `7:55`) — 36px leading icon circle,
/// title/timestamp, trailing signed amount (green credit, red debit).
class TransactionTile extends StatelessWidget {
  const TransactionTile({super.key, required this.transaction});

  final WalletTransaction transaction;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isCredit = transaction.type == WalletTransactionType.credit;
    final amountColor = isCredit ? const Color(0xFF0F9D58) : scheme.error;
    final sign = isCredit ? '+' : '−';
    final formattedAmount = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 2,
    ).format(transaction.amount.abs());
    final timestamp = DateFormat('d MMM yyyy, HH:mm').format(transaction.createdAt.toLocal());

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: amountColor.withValues(alpha: 0.12),
            child: Icon(_iconFor(transaction.source), size: 18, color: amountColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _titleFor(transaction.source),
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                ),
                const SizedBox(height: 2),
                Text(
                  timestamp,
                  style: TextStyle(fontSize: 11, color: Theme.of(context).hintColor),
                ),
              ],
            ),
          ),
          Text(
            '$sign$formattedAmount',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: amountColor),
          ),
        ],
      ),
    );
  }

  String _titleFor(WalletTransactionSource source) => switch (source) {
        WalletTransactionSource.topup => 'Wallet Recharge',
        WalletTransactionSource.rideFare => 'Ride Fare',
        WalletTransactionSource.refund => 'Refund',
        WalletTransactionSource.adminAdjustment => 'Admin Adjustment',
        WalletTransactionSource.unknown => 'Transaction',
      };

  IconData _iconFor(WalletTransactionSource source) => switch (source) {
        WalletTransactionSource.topup => Icons.add_card_outlined,
        WalletTransactionSource.rideFare => Icons.pedal_bike_outlined,
        WalletTransactionSource.refund => Icons.replay_outlined,
        WalletTransactionSource.adminAdjustment => Icons.tune_outlined,
        WalletTransactionSource.unknown => Icons.receipt_long_outlined,
      };
}
