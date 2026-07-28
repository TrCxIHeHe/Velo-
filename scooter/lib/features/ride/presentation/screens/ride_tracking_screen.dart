import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/app_snackbar.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/core/widgets/status_chip.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/fare_breakdown.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/router/app_router.dart';

/// Self-contained — watches the caller's active ride directly, so this
/// same widget works both as the "Ride" bottom-nav tab and as the
/// standalone route landed on right after a QR unlock is confirmed.
class RideTrackingScreen extends ConsumerStatefulWidget {
  const RideTrackingScreen({super.key});

  @override
  ConsumerState<RideTrackingScreen> createState() => _RideTrackingScreenState();
}

class _RideTrackingScreenState extends ConsumerState<RideTrackingScreen> {
  Timer? _tickTimer;
  bool _ending = false;

  @override
  void initState() {
    super.initState();
    // Re-render every second for the live duration/fare readout, and
    // periodically re-check the server in case the ride ended elsewhere.
    _tickTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) setState(() {});
      if (timer.tick % 15 == 0) ref.invalidate(activeRideProvider);
    });
  }

  @override
  void dispose() {
    _tickTimer?.cancel();
    super.dispose();
  }

  Future<void> _endRide(Ride ride) async {
    final dock = await _pickDock();
    if (dock == null || !mounted) return;

    setState(() => _ending = true);
    try {
      final ended = await ref.read(rideRepositoryProvider).endRide(ride.id, dock.id);
      ref.invalidate(activeRideProvider);
      if (!mounted) return;
      context.go(AppRoutes.rideReceiptPath(ended.id));
    } catch (e) {
      if (!mounted) return;
      setState(() => _ending = false);
      showAppSnackbar(context, e.toString(), isError: true);
    }
  }

  Future<Dock?> _pickDock() {
    final docksAsync = ref.read(dockListProvider);
    return showModalBottomSheet<Dock>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Return to which dock?', style: Theme.of(ctx).textTheme.titleMedium),
              const SizedBox(height: 12),
              Flexible(
                child: docksAsync.when(
                  loading: () => const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                  error: (e, _) => Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(e.toString()),
                  ),
                  data: (docks) => ListView(
                    shrinkWrap: true,
                    children: [
                      for (final dock in docks)
                        ListTile(
                          leading: const Icon(Icons.pedal_bike_outlined),
                          title: Text(dock.name),
                          onTap: () => Navigator.of(ctx).pop(dock),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final rideAsync = ref.watch(activeRideProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Ride')),
      body: rideAsync.when(
        loading: () => const StateView.loading(),
        error: (e, _) => StateView.error(
          subtitle: e.toString(),
          onRetry: () => ref.invalidate(activeRideProvider),
        ),
        data: (ride) {
          if (ride == null || ride.status != 'ACTIVE') {
            return const StateView.empty(
              subtitle: 'No active ride — unlock a scooter from the Map or Unlock tab',
            );
          }
          return _ActiveRideCard(
            ride: ride,
            ending: _ending,
            onEndRide: () => _endRide(ride),
          );
        },
      ),
    );
  }
}

class _ActiveRideCard extends StatelessWidget {
  const _ActiveRideCard({required this.ride, required this.ending, required this.onEndRide});

  final Ride ride;
  final bool ending;
  final VoidCallback onEndRide;

  @override
  Widget build(BuildContext context) {
    final startedAt = ride.startedAt ?? DateTime.now();
    final elapsedSeconds = DateTime.now().difference(startedAt).inSeconds.clamp(0, 1 << 30);
    final estFare = FareBreakdown.computeFare(elapsedSeconds);
    final currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Ride in progress', style: Theme.of(context).textTheme.titleMedium),
              const StatusChip(label: 'ACTIVE', variant: StatusChipVariant.success),
            ],
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _Stat(value: _formatDuration(elapsedSeconds), label: 'Duration'),
              _Stat(value: currency.format(estFare), label: 'Est. Fare'),
            ],
          ),
          const Spacer(),
          PrimaryButton(
            label: 'End Ride',
            loading: ending,
            onPressed: ending ? null : onEndRide,
          ),
        ],
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
