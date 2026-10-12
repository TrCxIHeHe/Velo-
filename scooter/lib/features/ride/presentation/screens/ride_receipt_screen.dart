import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:scooter/core/utils/money.dart';
import 'package:scooter/core/utils/server_time.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/fare_breakdown.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/router/app_router.dart';

class RideReceiptScreen extends ConsumerWidget {
  const RideReceiptScreen({super.key, required this.rideId});

  final String rideId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rideAsync = ref.watch(rideDetailProvider(rideId));

    // The receipt is reached with context.go, so there may be no stack to pop:
    // always send the user Home (system back included).
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) context.go(AppRoutes.home);
      },
      child: Scaffold(
      appBar: AppBar(
        title: const Text('Ride Receipt'),
        automaticallyImplyLeading: false,
        leading: IconButton(
          key: const Key('receipt-close'),
          icon: const Icon(Icons.close),
          onPressed: () => context.go(AppRoutes.home),
        ),
      ),
      body: rideAsync.when(
        loading: () => const StateView.loading(),
        error: (e, _) => StateView.error(
          subtitle: e.toString(),
          onRetry: () => ref.invalidate(rideDetailProvider(rideId)),
        ),
        data: (ride) {
          final durationSeconds = ride.durationSeconds ?? 0;
          final fareAmount = ride.fareAmount ?? 0;
          // Dock names are presentation only; the fare itself is ride.fareAmount.
          final originName = ref.watch(dockByIdProvider(ride.startDockId)).valueOrNull?.name;
          final destinationName =
              ride.endDockId == null ? null : ref.watch(dockByIdProvider(ride.endDockId!)).valueOrNull?.name;
          final breakdown = FareBreakdown.fromRide(
            fareAmount: fareAmount,
            pricingStrategy: ride.pricingStrategy,
            originName: originName,
            destinationName: destinationName,
          );
          final scheme = Theme.of(context).colorScheme;
          String money(num v) => formatMoney(v, ride.fareCurrency);

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
                        value: formatElapsed(Duration(seconds: durationSeconds)),
                        label: 'Duration',
                      ),
                      _Stat(
                        value: money(fareAmount),
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
                                money(item.amount),
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
                              money(breakdown.total),
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
                  key: const Key('receipt-done'),
                  label: 'Done',
                  onPressed: () => context.go(AppRoutes.home),
                ),
              ],
            ),
          );
        },
      ),
      ),
    );
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
