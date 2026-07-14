import 'dart:async';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/presentation/providers/active_ride_providers.dart';
import 'package:scooter/features/ride/presentation/providers/active_ride_state.dart';

/// Read-only ride tracking. No "End Ride" action — Phase 4 (billing/fare)
/// hasn't landed on the backend, and there's no end-ride endpoint yet.
/// No live location — no vehicle telemetry endpoint is exposed to riders.
class RideTrackingScreen extends ConsumerStatefulWidget {
  const RideTrackingScreen({super.key});

  @override
  ConsumerState<RideTrackingScreen> createState() =>
      _RideTrackingScreenState();
}

class _RideTrackingScreenState extends ConsumerState<RideTrackingScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(activeRideNotifierProvider.notifier).resume();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(activeRideNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Your Ride')),
      body: switch (state) {
        ActiveRideNone() => const _NoRideBody(),
        ActiveRideLoading() => const Center(child: CircularProgressIndicator()),
        ActiveRideTracking(:final ride) => _TrackingBody(ride: ride),
        ActiveRideEnded(:final ride) => _EndedBody(
            ride: ride,
            onDismiss: () =>
                ref.read(activeRideNotifierProvider.notifier).dismiss(),
          ),
        ActiveRideError(:final message) => _ErrorBody(
            message: message,
            onRetry: () =>
                ref.read(activeRideNotifierProvider.notifier).resume(),
          ),
      },
    );
  }
}

// ── No active ride ─────────────────────────────────────────────────────────────

class _NoRideBody extends StatelessWidget {
  const _NoRideBody();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.electric_scooter_outlined,
                size: 64, color: colorScheme.outlineVariant),
            const SizedBox(height: 16),
            Text(
              'No active ride',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Scan a scooter from the Unlock tab to start a ride.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: colorScheme.outline,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Active tracking card ────────────────────────────────────────────────────────

class _TrackingBody extends ConsumerStatefulWidget {
  const _TrackingBody({required this.ride});

  final Ride ride;

  @override
  ConsumerState<_TrackingBody> createState() => _TrackingBodyState();
}

class _TrackingBodyState extends ConsumerState<_TrackingBody> {
  Timer? _clock;

  @override
  void initState() {
    super.initState();
    // Local 1s tick purely to redraw the elapsed-time counter between polls.
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _clock?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ride = widget.ride;
    final colorScheme = Theme.of(context).colorScheme;

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(activeRideNotifierProvider.notifier).refreshNow(),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _StatusBanner(status: ride.status),
          const SizedBox(height: 20),
          _ActiveRideCard(ride: ride),
          const SizedBox(height: 20),
          if (ride.status == 'ACTIVE')
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline,
                      size: 18, color: colorScheme.outline),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Fare and ride-ending are coming soon. Return the '
                      'scooter to any dock — your ride will update here.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: colorScheme.outline,
                          ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final (label, color, icon) = switch (status) {
      'ASSIGNED' => (
          'Scooter reserved — scan to unlock',
          Colors.amber.shade700,
          Icons.hourglass_top_rounded,
        ),
      'UNLOCK_PENDING' => (
          'Unlocking…',
          Colors.amber.shade700,
          Icons.lock_open_rounded,
        ),
      'ACTIVE' => (
          'Ride in progress',
          Colors.green.shade700,
          Icons.electric_scooter_rounded,
        ),
      'END_PENDING' => (
          'Ending ride…',
          Colors.blue.shade700,
          Icons.flag_rounded,
        ),
      _ => (status, Theme.of(context).colorScheme.outline, Icons.circle),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActiveRideCard extends StatelessWidget {
  const _ActiveRideCard({required this.ride});

  final Ride ride;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final elapsed = ride.startAt != null
        ? DateTime.now().toUtc().difference(ride.startAt!.toUtc())
        : null;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: colorScheme.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.electric_scooter_rounded,
                  color: colorScheme.onPrimary, size: 28),
              const SizedBox(width: 10),
              Text(
                'Active Ride',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: colorScheme.onPrimary,
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (elapsed != null) ...[
            Text(
              _formatDuration(elapsed),
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                    color: colorScheme.onPrimary,
                    fontWeight: FontWeight.bold,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
            ),
            Text(
              'Elapsed time',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: colorScheme.onPrimary.withOpacity(0.7),
                  ),
            ),
            const SizedBox(height: 20),
          ],
          _CardRow(
            label: 'Vehicle',
            value: ride.vehicleId != null
                ? '#${ride.vehicleId!.substring(0, 8).toUpperCase()}'
                : '—',
            color: colorScheme.onPrimary,
          ),
          if (ride.startAt != null)
            _CardRow(
              label: 'Started',
              value: _formatTime(ride.startAt!),
              color: colorScheme.onPrimary,
            ),
        ],
      ),
    );
  }

  String _formatDuration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes % 60;
    final s = d.inSeconds % 60;
    final mm = m.toString().padLeft(2, '0');
    final ss = s.toString().padLeft(2, '0');
    return h > 0 ? '$h:$mm:$ss' : '$mm:$ss';
  }

  String _formatTime(DateTime dt) {
    final local = dt.toLocal();
    return '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }
}

class _CardRow extends StatelessWidget {
  const _CardRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: color.withOpacity(0.7),
                ),
          ),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ],
      ),
    );
  }
}

// ── Ended ────────────────────────────────────────────────────────────────────────

class _EndedBody extends StatelessWidget {
  const _EndedBody({required this.ride, required this.onDismiss});

  final Ride ride;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isSuccess = ride.status == 'COMPLETED';

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSuccess ? Icons.check_circle_outline : Icons.cancel_outlined,
              size: 64,
              color: isSuccess ? Colors.green.shade700 : colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              isSuccess ? 'Ride Completed' : 'Ride ${ride.status}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (ride.fare != null) ...[
              const SizedBox(height: 8),
              Text(
                '₹${ride.fare!.toStringAsFixed(2)}',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: onDismiss,
              child: const Text('Done'),
            ),
          ],
        ),
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
                size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
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
