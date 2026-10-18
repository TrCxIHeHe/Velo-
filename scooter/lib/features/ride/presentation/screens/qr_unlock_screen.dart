import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/core/utils/money.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/features/ride/presentation/widgets/destination_picker_sheet.dart';
import 'package:scooter/router/app_router.dart';

enum _Status { planning, requesting, showing, confirmed, expired, error }

class QrUnlockScreen extends ConsumerStatefulWidget {
  const QrUnlockScreen({super.key, required this.dockId});

  final String dockId;

  @override
  ConsumerState<QrUnlockScreen> createState() => _QrUnlockScreenState();
}

class _QrUnlockScreenState extends ConsumerState<QrUnlockScreen>
    with WidgetsBindingObserver {
  _Status _status = _Status.planning;
  RideToken? _token;
  int _secondsRemaining = 0;
  Timer? _countdownTimer;
  Timer? _pollTimer;
  String? _error;
  Dock? _destination;

  /// Absolute moment after which the QR must no longer be shown as valid.
  ///
  /// Taken from the clock *before* the token request is sent. The backend
  /// stamps the token (iat) after receiving that request, so this deadline is
  /// always at or slightly BEFORE the real server-side expiry: the UI can
  /// never present a QR as valid after the backend has already rejected it.
  /// Using an absolute deadline (rather than decrementing a counter) also
  /// keeps the display correct after the app was backgrounded or a timer was
  /// delayed.
  DateTime? _deadline;

  /// Incremented for every token request so a slow, superseded request can
  /// never overwrite the state of a newer one.
  int _generation = 0;

  late final RideRepository _rideRepo;

  @override
  void initState() {
    super.initState();
    _rideRepo = ref.read(rideRepositoryProvider);
    WidgetsBinding.instance.addObserver(this);
    // The ride does not exist until the user confirms this plan. Keep the
    // origin/destination/fare selection ahead of token creation.
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _countdownTimer?.cancel();
    _pollTimer?.cancel();

    // Leaving while a code is still live: cancel it server-side so it cannot
    // linger as PENDING. Best effort — the backend expires it on its own
    // anyway once the 30 s token lifetime elapses.
    final token = _token;
    if (_status == _Status.showing && token != null) {
      _rideRepo
          .cancelRide(token.rideId)
          .then<void>((_) {}, onError: (Object _) {});
    }
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _status == _Status.showing) {
      _tickCountdown(); // re-evaluate against the deadline immediately
      if (_status == _Status.showing) _checkRideStatus();
    }
  }

  Future<void> _requestToken() async {
    _countdownTimer?.cancel();
    _pollTimer?.cancel();
    final generation = ++_generation;
    setState(() {
      _status = _Status.requesting;
      _error = null;
    });

    final requestedAt = DateTime.now();
    try {
      final token = await _rideRepo.requestToken(
        widget.dockId,
        destinationDockId: _destination!.id,
      );
      if (!mounted) {
        // The user left while the request was in flight: the server already
        // created a PENDING ride, so retire it (best effort; it would also
        // expire on its own). If it was activated meanwhile the server refuses
        // (RIDE_INVALID_STATE) and the active ride is left untouched.
        _rideRepo
            .cancelRide(token.rideId)
            .then<void>((_) {}, onError: (Object _) {});
        return;
      }

      if (generation != _generation) return;
      setState(() {
        _token = token;
        _deadline = requestedAt.add(Duration(seconds: token.expiresInSeconds));
        _secondsRemaining = token.expiresInSeconds;
        _status = _Status.showing;
      });
      _startCountdown();
      _startPolling(token.rideId, generation);
    } catch (e) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _status = _Status.error;
        _error = e.toString();
      });
    }
  }

  Future<void> _pickDestination() async {
    final destination = await DestinationPickerSheet.show(
      context,
      ref,
      originDockId: widget.dockId,
      selectedDockId: _destination?.id,
    );
    if (destination != null && mounted) {
      setState(() => _destination = destination);
    }
  }

  void _startCountdown() {
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(
      const Duration(milliseconds: 250),
      (_) => _tickCountdown(),
    );
    _tickCountdown();
  }

  void _tickCountdown() {
    if (!mounted || _status != _Status.showing || _deadline == null) return;
    final remainingMs = _deadline!.difference(DateTime.now()).inMilliseconds;
    if (remainingMs <= 0) {
      _markExpired();
      return;
    }
    final seconds = (remainingMs / 1000).ceil();
    if (seconds != _secondsRemaining) {
      setState(() => _secondsRemaining = seconds);
    }
  }

  /// Stop presenting the QR as valid and offer a new one.
  void _markExpired() {
    _countdownTimer?.cancel();
    _pollTimer?.cancel();
    if (!mounted || _status != _Status.showing) return;
    final rideId = _token?.rideId;
    setState(() {
      _secondsRemaining = 0;
      _status = _Status.expired;
    });
    // A scan can land in the last instant before expiry; reconcile once with
    // the backend so we never show "expired" for a ride that actually started.
    if (rideId != null) _reconcileAfterExpiry(rideId);
  }

  Future<void> _reconcileAfterExpiry(String rideId) async {
    try {
      final ride = await _rideRepo.getRide(rideId);
      if (!mounted || _status != _Status.expired) return;
      if (ride.status == 'ACTIVE') _onConfirmed();
    } catch (_) {
      // Offline — the expired state is still the safe thing to show.
    }
  }

  void _onConfirmed() {
    _pollTimer?.cancel();
    _countdownTimer?.cancel();
    if (!mounted) return;
    setState(() => _status = _Status.confirmed);
    ref.invalidate(activeRideProvider);
    context.go(AppRoutes.rideActivePath);
  }

  /// One status check of THIS ride (authoritative backend state).
  Future<void> _checkRideStatus() async {
    final token = _token;
    if (token == null || !mounted || _status != _Status.showing) return;
    final generation = _generation;
    try {
      final ride = await _rideRepo.getRide(token.rideId);
      if (!mounted || generation != _generation || _status != _Status.showing) {
        return;
      }
      switch (ride.status) {
        case 'ACTIVE':
          _onConfirmed();
        case 'EXPIRED':
        case 'CANCELLED':
          _markExpired(); // backend says this code is dead
        default:
          break; // PENDING — keep showing
      }
    } catch (_) {
      // transient network hiccup — keep trying until expiry
    }
  }

  /// Adaptive polling with backoff to reduce server load (B-08).
  ///
  /// Phase 1  (0–10 s elapsed): poll every 2 s — fast feedback for the
  ///           common case where the ESP32 scans quickly.
  /// Phase 2 (10–30 s elapsed): poll every 4 s — scan is taking longer,
  ///           no need to hammer the API.
  /// Phase 3     (30 s+)      : poll every 6 s — approaching token expiry;
  ///           keep trying but at minimal cost.
  ///
  /// Polls the specific ride (GET /rides/{id}) instead of "the active ride",
  /// so the screen sees ACTIVE *and* EXPIRED/CANCELLED and cannot drift from
  /// the backend's view of the token.
  void _startPolling(String rideId, int generation) {
    final stopwatch = Stopwatch()..start();

    void scheduleNext(void Function() tick) {
      if (!mounted || generation != _generation || _status != _Status.showing) {
        return;
      }
      final elapsed = stopwatch.elapsed.inSeconds;
      final interval = elapsed < 10
          ? const Duration(seconds: 2)
          : elapsed < 30
          ? const Duration(seconds: 4)
          : const Duration(seconds: 6);
      _pollTimer = Timer(interval, tick);
    }

    void tick() async {
      if (!mounted || generation != _generation || _status != _Status.showing) {
        return;
      }
      await _checkRideStatus();
      scheduleNext(tick);
    }

    scheduleNext(tick);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan to Unlock')),
      body: SafeArea(child: Center(child: _buildBody())),
    );
  }

  Widget _buildBody() {
    switch (_status) {
      case _Status.planning:
        return _buildPlan();
      case _Status.requesting:
      case _Status.confirmed:
        return const StateView.loading(subtitle: 'Preparing your unlock code…');
      case _Status.error:
        return StateView.error(
          subtitle: _error ?? 'Please try again.',
          onRetry: _requestToken,
        );
      case _Status.expired:
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('⏱️', style: TextStyle(fontSize: 40)),
              const SizedBox(height: 12),
              Text(
                'Code expired',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'This code is no longer valid. Generate a new one to try again.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Theme.of(context).hintColor),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: 200,
                child: PrimaryButton(
                  label: 'Generate new code',
                  onPressed: _requestToken,
                ),
              ),
            ],
          ),
        );
      case _Status.showing:
        final scheme = Theme.of(context).colorScheme;
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Show this at the dock scanner',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 32),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
                child: QrImageView(
                  data: _token!.rideToken,
                  size: 280,
                  backgroundColor: Colors.white,
                  errorCorrectionLevel: QrErrorCorrectLevel.L,
                ),
              ),
              const SizedBox(height: 32),
              CircleAvatar(
                radius: 40,
                backgroundColor: scheme.primary,
                child: Text(
                  '$_secondsRemaining',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: scheme.onPrimary,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Seconds remaining',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'One-time use · ${_token!.expiresInSeconds} second window',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).hintColor,
                ),
              ),
            ],
          ),
        );
    }
  }

  Widget _buildPlan() {
    final origin = ref.watch(dockByIdProvider(widget.dockId));
    final quoteAsync = _destination == null
        ? null
        : ref.watch(
            preRideFareQuoteProvider((
              originDockId: widget.dockId,
              destinationDockId: _destination!.id,
            )),
          );
    final quote = quoteAsync?.valueOrNull;
    final canStart =
        _destination != null && quote != null && !quoteAsync!.isLoading;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Plan your ride', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            origin.when(
              loading: () => 'From your selected dock…',
              error: (e, _) => e.toString(),
              data: (dock) => 'From ${dock.name}',
            ),
          ),
          const SizedBox(height: 16),
          OutlinedButton(
            key: const Key('pre-ride-destination'),
            onPressed: _pickDestination,
            child: Text(
              _destination == null
                  ? 'Choose destination'
                  : 'To ${_destination!.name}',
            ),
          ),
          const SizedBox(height: 16),
          if (_destination == null)
            const Text(
              'Choose a destination to see your fare.',
              key: Key('pre-ride-fare-hint'),
            )
          else if (quoteAsync!.isLoading)
            const LinearProgressIndicator(key: Key('pre-ride-fare-loading'))
          else if (quoteAsync.hasError)
            Row(
              key: const Key('pre-ride-fare-error'),
              children: [
                Expanded(child: Text(quoteAsync.error.toString())),
                TextButton(
                  onPressed: () => ref.invalidate(
                    preRideFareQuoteProvider((
                      originDockId: widget.dockId,
                      destinationDockId: _destination!.id,
                    )),
                  ),
                  child: const Text('Retry'),
                ),
              ],
            )
          else
            Text(
              '${formatMoney(quote!.fareAmount, quote.currency)} estimated fare',
              key: const Key('pre-ride-fare'),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          const SizedBox(height: 24),
          PrimaryButton(
            key: const Key('start-ride-button'),
            label: 'Start ride',
            onPressed: canStart ? _requestToken : null,
          ),
        ],
      ),
    );
  }
}
