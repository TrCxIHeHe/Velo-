import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/router/app_router.dart';

enum _Status { requesting, showing, confirmed, expired, error }

class QrUnlockScreen extends ConsumerStatefulWidget {
  const QrUnlockScreen({super.key, required this.dockId});

  final String dockId;

  @override
  ConsumerState<QrUnlockScreen> createState() => _QrUnlockScreenState();
}

class _QrUnlockScreenState extends ConsumerState<QrUnlockScreen> {
  _Status _status = _Status.requesting;
  RideToken? _token;
  int _secondsRemaining = 0;
  Timer? _countdownTimer;
  Timer? _pollTimer;
  String? _error;

  @override
  void initState() {
    super.initState();
    _requestToken();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _requestToken() async {
    _countdownTimer?.cancel();
    _pollTimer?.cancel();
    setState(() {
      _status = _Status.requesting;
      _error = null;
    });

    try {
      final token = await ref.read(rideRepositoryProvider).requestToken(widget.dockId);
      if (!mounted) return;
      setState(() {
        _token = token;
        _secondsRemaining = token.expiresInSeconds;
        _status = _Status.showing;
      });
      _startCountdown();
      _startPolling(token.rideId);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _status = _Status.error;
        _error = e.toString();
      });
    }
  }

  void _startCountdown() {
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return;
      if (_secondsRemaining <= 1) {
        timer.cancel();
        _pollTimer?.cancel();
        setState(() {
          _secondsRemaining = 0;
          if (_status == _Status.showing) _status = _Status.expired;
        });
        return;
      }
      setState(() => _secondsRemaining -= 1);
    });
  }

  void _startPolling(String rideId) {
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      if (!mounted || _status != _Status.showing) return;
      try {
        final active = await ref.read(rideRepositoryProvider).getActiveRide();
        if (active != null && active.id == rideId && active.status == 'ACTIVE') {
          timer.cancel();
          _countdownTimer?.cancel();
          if (!mounted) return;
          setState(() => _status = _Status.confirmed);
          ref.invalidate(activeRideProvider);
          if (!mounted) return;
          context.go(AppRoutes.rideActivePath);
        }
      } catch (_) {
        // transient network hiccup while polling — keep trying until expiry
      }
    });
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
      case _Status.requesting:
      case _Status.confirmed:
        return const StateView.loading(subtitle: 'Preparing your unlock code…');
      case _Status.error:
        return StateView.error(subtitle: _error ?? 'Please try again.', onRetry: _requestToken);
      case _Status.expired:
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('⏱️', style: TextStyle(fontSize: 40)),
              const SizedBox(height: 12),
              Text('Code expired', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(
                'The unlock window closed. Generate a new one to try again.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Theme.of(context).hintColor),
              ),
              const SizedBox(height: 24),
              SizedBox(width: 200, child: PrimaryButton(label: 'Try again', onPressed: _requestToken)),
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
                  border: Border.all(color: Theme.of(context).colorScheme.outline),
                ),
                child: QrImageView(
                  data: _token!.rideToken,
                  size: 220,
                  backgroundColor: Colors.white,
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
              Text('Seconds remaining', style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 8),
              Text(
                'One-time use · ${_token!.expiresInSeconds} second window',
                style: TextStyle(fontSize: 12, color: Theme.of(context).hintColor),
              ),
            ],
          ),
        );
    }
  }
}
