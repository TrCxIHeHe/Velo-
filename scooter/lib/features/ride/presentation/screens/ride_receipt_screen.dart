import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/features/ride/domain/fare_breakdown.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';

class RideReceiptScreen extends ConsumerWidget {
  const RideReceiptScreen({super.key, required this.rideId});

  final String rideId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rideAsync = ref.watch(rideDetailProvider(rideId));

    return Scaffold(
      appBar: AppBar(title: const Text('Ride Receipt')),
      body: rideAsync.when(
        loading: () => const StateView.loading(),
        error: (e, _) => StateView.error(
          subtitle: e.toString(),
          onRetry: () => ref.invalidate(rideDetailProvider(rideId)),
        ),
        data: (ride) {
          final durationSeconds = ride.durationSeconds ?? 0;
          final fareAmount = ride.fareAmount ?? 0;
          final breakdown = FareBreakdown.fromRide(
            durationSeconds: durationSeconds,
            fareAmount: fareAmount,
          );
          final scheme = Theme.of(context).colorScheme;
          final currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

          return SafeArea(
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Center(
                  child: Column(
                    children: [
                      Icon(Icons.check_circle, size: 56, color: scheme.primary),
                      const SizedBox(height: 12),
                      Text('Ride completed', style: Theme.of(context).textTheme.headlineSmall),
                      if (ride.endedAt != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          DateFormat('d MMM yyyy, HH:mm').format(ride.endedAt!.toLocal()),
                          style: TextStyle(color: Theme.of(context).hintColor, fontSize: 13),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 32),
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: scheme.outline),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _Stat(
                        value: _formatDuration(durationSeconds),
                        label: 'Duration',
                      ),
                      _Stat(
                        value: currency.format(fareAmount),
                        label: 'Total Fare',
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                Text('Fare breakdown', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                  decoration: BoxDecoration(
                    color: Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: scheme.outline),
                  ),
                  child: Column(
                    children: [
                      for (final item in breakdown.lineItems)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text(item.label, style: Theme.of(context).textTheme.bodyLarge),
                              ),
                              Text(
                                currency.format(item.amount),
                                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                              ),
                            ],
                          ),
                        ),
                      Divider(color: scheme.outline),
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Total charged', style: TextStyle(fontWeight: FontWeight.w700)),
                            Text(
                              currency.format(breakdown.total),
                              style: TextStyle(fontWeight: FontWeight.w700, color: scheme.primary),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 40),
                PrimaryButton(
                  label: 'Done',
                  onPressed: () => context.canPop() ? context.pop() : context.go('/'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  String _formatDuration(int seconds) {
    final minutes = seconds ~/ 60;
    final remainingSeconds = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${remainingSeconds.toString().padLeft(2, '0')}';
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label});
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 2),
        Text(label, style: TextStyle(fontSize: 11, color: Theme.of(context).hintColor)),
      ],
    );
  }
}
