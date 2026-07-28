import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Card — Balance (Figma component library `3:15` / screen "08 · Wallet").
/// Brand-filled, radius 20, "Balance" label / big amount / currency code.
class BalanceCard extends StatelessWidget {
  const BalanceCard({super.key, required this.balance, required this.currency});

  final double balance;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final formatted = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 2,
    ).format(balance);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
      decoration: BoxDecoration(
        color: scheme.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Balance',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: scheme.onPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            formatted,
            style: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w700,
              color: scheme.onPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            currency,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w400,
              color: scheme.onPrimary.withValues(alpha: 0.85),
            ),
          ),
        ],
      ),
    );
  }
}
