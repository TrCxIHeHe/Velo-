import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/core/utils/money.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/app_snackbar.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/features/dock/domain/eligible_destinations.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/models/fare_quote.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/features/ride/presentation/widgets/destination_picker_sheet.dart';
import 'package:scooter/features/ride/presentation/widgets/elapsed_duration.dart';
import 'package:scooter/features/ride/presentation/widgets/ride_map.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';
import 'package:scooter/router/app_router.dart';

/// Builds the map area. Overridable so widget tests do not need real tiles.
typedef RideMapBuilder = Widget Function(BuildContext context, RideMapData data, ValueChanged<Dock> onSelect);

/// Active-ride screen. Self-contained (watches the caller's active ride), so
/// the same widget serves as the "Ride" bottom-nav tab ([standalone] = false)
/// and as the standalone `/ride/active` route reached after a QR unlock
/// ([standalone] = true, which adds a back action to Home).
class RideTrackingScreen extends ConsumerStatefulWidget {
  const RideTrackingScreen({super.key, this.standalone = false, this.mapBuilder, this.now = DateTime.now});

  final bool standalone;
  final RideMapBuilder? mapBuilder;

  /// Injectable clock (tests).
  final DateTime Function() now;

  @override
  ConsumerState<RideTrackingScreen> createState() => _RideTrackingScreenState();
}

class _RideTrackingScreenState extends ConsumerState<RideTrackingScreen> {
  static const _syncInterval = Duration(seconds: 15);

  Timer? _syncTimer;
  Dock? _destination;
  String? _destinationRideId;

  /// True from tapping End Ride until the request settles: blocks double submits.
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // Reconcile with the backend periodically (e.g. the ride ended elsewhere).
    // The ride is kept on screen while this refresh runs — see build().
    _syncTimer = Timer.periodic(_syncInterval, (_) {
      if (mounted && !_busy) ref.invalidate(activeRideProvider);
    });
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    super.dispose();
  }

  void _goHome() => context.go(AppRoutes.home);

  void _selectDestination(Ride ride, Dock dock) {
    if (_busy) return;
    setState(() {
      _destination = dock;
      _destinationRideId = ride.id;
    });
  }

  Future<void> _pickDestination(Ride ride) async {
    final dock = await DestinationPickerSheet.show(
      context,
      ref,
      originDockId: ride.startDockId,
      selectedDockId: _destinationFor(ride)?.id,
    );
    if (dock != null && mounted) _selectDestination(ride, dock);
  }

  Dock? _destinationFor(Ride ride) => _destinationRideId == ride.id ? _destination : null;

  Future<void> _confirmAndEnd(Ride ride, Dock destination, FareQuote quote) async {
    if (_busy) return;
    setState(() => _busy = true);

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('End ride?'),
        content: Text(
          'Park at ${destination.name}. ${formatMoney(quote.fareAmount, quote.currency)} '
          'will be charged to your wallet.',
        ),
        actions: [
          TextButton(key: const Key('end-cancel'), onPressed: () => Navigator.pop(ctx, false), child: const Text('Not yet')),
          FilledButton(key: const Key('end-confirm'), onPressed: () => Navigator.pop(ctx, true), child: const Text('End ride')),
        ],
      ),
    );
    if (confirmed != true) {
      if (mounted) setState(() => _busy = false);
      return;
    }

    try {
      final ended = await ref.read(rideRepositoryProvider).endRide(ride.id, destination.id);
      // Navigate only after the backend confirmed the ride is completed.
      ref.invalidate(activeRideProvider);
      ref.invalidate(dockListProvider);
      try {
        unawaited(ref.read(walletNotifierProvider.notifier).refresh());
      } catch (_) {
        // balance refresh is best effort; the wallet tab reloads on open anyway
      }
      if (!mounted) return;
      context.go(AppRoutes.rideReceiptPath(ended.id));
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      final code = e is ApiException ? e.code : null;
      if (code == 'DOCK_FULL' || code == 'DOCK_NOT_FOUND') {
        // The chosen dock is no longer usable: drop it, refresh availability and
        // let the user pick another dock and get a fresh quote.
        setState(() {
          _destination = null;
          _destinationRideId = null;
        });
        ref.invalidate(dockListProvider);
      }
      showAppSnackbar(context, e.toString(), isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rideAsync = ref.watch(activeRideProvider);
    // `valueOrNull`, not `.when`: after an invalidate/refresh the previous ride
    // stays on screen instead of flashing a full-screen spinner every 15 s.
    final ride = rideAsync.valueOrNull;

    Widget body;
    if (!rideAsync.hasValue) {
      body = rideAsync.hasError
          ? StateView.error(
              subtitle: rideAsync.error.toString(),
              onRetry: () => ref.invalidate(activeRideProvider),
            )
          : const StateView.loading(subtitle: 'Loading your ride…');
    } else if (ride == null || !ride.isActive) {
      body = const StateView.empty(
        title: 'No active ride',
        subtitle: 'Unlock a scooter from the Map or Unlock tab to start riding.',
      );
    } else {
      body = _ActiveRide(
        ride: ride,
        destination: _destinationFor(ride),
        busy: _busy,
        stale: rideAsync.hasError,
        now: widget.now,
        mapBuilder: widget.mapBuilder,
        onRetrySync: () => ref.invalidate(activeRideProvider),
        onPickDestination: () => _pickDestination(ride),
        onSelectDock: (dock) => _selectDestination(ride, dock),
        onEnd: _confirmAndEnd,
      );
    }

    return PopScope(
      // Standalone route: back must go Home (the stack may be empty after
      // context.go) and must never end/cancel the ride.
      canPop: !widget.standalone,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && widget.standalone) _goHome();
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Ride'),
          automaticallyImplyLeading: false,
          leading: widget.standalone
              ? IconButton(
                  key: const Key('ride-back'),
                  tooltip: 'Back to home',
                  icon: const Icon(Icons.arrow_back),
                  onPressed: _goHome,
                )
              : null,
        ),
        body: SafeArea(top: false, child: body),
      ),
    );
  }
}

class _ActiveRide extends ConsumerWidget {
  const _ActiveRide({
    required this.ride,
    required this.destination,
    required this.busy,
    required this.stale,
    required this.now,
    required this.mapBuilder,
    required this.onRetrySync,
    required this.onPickDestination,
    required this.onSelectDock,
    required this.onEnd,
  });

  final Ride ride;
  final Dock? destination;
  final bool busy;
  final bool stale;
  final DateTime Function() now;
  final RideMapBuilder? mapBuilder;
  final VoidCallback onRetrySync;
  final VoidCallback onPickDestination;
  final ValueChanged<Dock> onSelectDock;
  final Future<void> Function(Ride, Dock, FareQuote) onEnd;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final muted = Theme.of(context).hintColor;
    final docksAsync = ref.watch(dockListProvider);
    final originAsync = ref.watch(dockByIdProvider(ride.startDockId));

    final eligible = docksAsync.hasValue
        ? eligibleDestinations(docksAsync.requireValue, originDockId: ride.startDockId)
        : const <Dock>[];
    final mapData = RideMapData(origin: originAsync.valueOrNull, destinations: eligible, selected: destination);

    final quoteAsync = destination == null
        ? null
        : ref.watch(fareQuoteProvider((rideId: ride.id, destinationDockId: destination!.id)));
    final quote = quoteAsync?.valueOrNull;
    final canEnd = !busy && destination != null && quote != null && !(quoteAsync?.isLoading ?? true);

    final map = mapBuilder != null
        ? mapBuilder!(context, mapData, onSelectDock)
        : RideMap(data: mapData, onSelectDock: onSelectDock);

    return Column(
      children: [
        if (stale)
          Material(
            color: scheme.errorContainer,
            child: ListTile(
              key: const Key('stale-banner'),
              dense: true,
              leading: Icon(Icons.sync_problem, color: scheme.onErrorContainer),
              title: Text(
                "Couldn't refresh — showing your last known ride",
                style: TextStyle(color: scheme.onErrorContainer, fontSize: 13),
              ),
              trailing: TextButton(onPressed: onRetrySync, child: const Text('Retry')),
            ),
          ),
        // Header: status + live duration
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.circle, size: 10, color: Colors.green.shade600),
                      const SizedBox(width: 6),
                      const Text('Ride in progress', key: Key('ride-status'), style: TextStyle(fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text('Duration', style: TextStyle(fontSize: 11, color: muted)),
                ],
              ),
              if (ride.startedAt != null)
                ElapsedDuration(startedAt: ride.startedAt!, now: now)
              else
                const Text('--:--', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
        Expanded(child: map),
        ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.5),
          child: Material(
            elevation: 8,
            color: Theme.of(context).cardColor,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _DestinationRow(
                    destination: destination,
                    origin: originAsync.valueOrNull,
                    enabled: !busy,
                    onTap: onPickDestination,
                  ),
                  const SizedBox(height: 12),
                  _FareSection(
                    destination: destination,
                    quoteAsync: quoteAsync,
                    onRetry: () {
                      if (destination != null) {
                        ref.invalidate(fareQuoteProvider((rideId: ride.id, destinationDockId: destination!.id)));
                      }
                    },
                  ),
                  const SizedBox(height: 16),
                  PrimaryButton(
                    key: const Key('end-ride-button'),
                    label: 'End Ride',
                    loading: busy,
                    onPressed: canEnd ? () => onEnd(ride, destination!, quote!) : null,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _DestinationRow extends StatelessWidget {
  const _DestinationRow({required this.destination, required this.origin, required this.enabled, required this.onTap});

  final Dock? destination;
  final Dock? origin;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).hintColor;
    return InkWell(
      key: const Key('destination-button'),
      onTap: enabled ? onTap : null,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outline),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.flag_outlined),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    destination == null ? 'Choose where to return' : destination!.name,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  if (origin != null)
                    Text('From ${origin!.name}', style: TextStyle(fontSize: 12, color: muted)),
                ],
              ),
            ),
            Text(destination == null ? 'Select' : 'Change', style: TextStyle(color: Theme.of(context).colorScheme.primary)),
          ],
        ),
      ),
    );
  }
}

class _FareSection extends StatelessWidget {
  const _FareSection({required this.destination, required this.quoteAsync, required this.onRetry});

  final Dock? destination;
  final AsyncValue<FareQuote>? quoteAsync;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).hintColor;
    final scheme = Theme.of(context).colorScheme;

    // No fare is shown as if valid before a destination has been quoted. A
    // destination change creates a new quote provider (loading), so the
    // previous destination's fare can never linger here.
    if (destination == null || quoteAsync == null) {
      return Text(
        'Select a destination to see your fare.',
        key: const Key('fare-hint'),
        style: TextStyle(color: muted),
      );
    }

    final async = quoteAsync!;
    if (async.isLoading) {
      return Row(
        key: const Key('fare-loading'),
        children: [
          const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          const SizedBox(width: 12),
          Text('Calculating fare…', style: TextStyle(color: muted)),
        ],
      );
    }
    if (async.hasError) {
      return Row(
        key: const Key('fare-error'),
        children: [
          Icon(Icons.error_outline, color: scheme.error),
          const SizedBox(width: 8),
          Expanded(child: Text(async.error.toString(), style: TextStyle(color: scheme.error, fontSize: 13))),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      );
    }

    final quote = async.requireValue;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Estimated fare', style: TextStyle(fontSize: 12, color: muted)),
        const SizedBox(height: 2),
        Text(
          formatMoney(quote.fareAmount, quote.currency),
          key: const Key('fare-amount'),
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700),
        ),
        Text('Fixed fare for this route · ${quote.currency}', style: TextStyle(fontSize: 12, color: muted)),
        if (quote.sufficientBalance == false)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Your wallet balance may not cover this fare. Top up before ending.',
              key: const Key('fare-balance-warning'),
              style: TextStyle(fontSize: 12, color: scheme.error),
            ),
          ),
      ],
    );
  }
}
