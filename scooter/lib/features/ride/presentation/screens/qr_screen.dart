import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/presentation/providers/ride_token_providers.dart';
import 'package:scooter/features/ride/presentation/providers/ride_token_state.dart';

class QrScreen extends ConsumerStatefulWidget {
  const QrScreen({super.key});

  @override
  ConsumerState<QrScreen> createState() => _QrScreenState();
}

class _QrScreenState extends ConsumerState<QrScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(rideTokenNotifierProvider.notifier).requestAndIssue();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(rideTokenNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Scan to Unlock')),
      body: SafeArea(
        child: switch (state) {
          RideTokenInitial() || RideTokenLoading() => const _LoadingBody(),
          RideTokenActive(:final token) => _ActiveBody(token: token),
          RideTokenExpired() => _ExpiredBody(
              onRegenerate: () => ref
                  .read(rideTokenNotifierProvider.notifier)
                  .regenerate(),
            ),
          RideTokenError(:final message, :final code) => _ErrorBody(
              message: message,
              code: code,
              onRetry: () => ref
                  .read(rideTokenNotifierProvider.notifier)
                  .requestAndIssue(),
            ),
        },
      ),
    );
  }
}

// ── Active state — QR + countdown ─────────────────────────────────────────────

class _ActiveBody extends ConsumerStatefulWidget {
  const _ActiveBody({required this.token});

  final RideToken token;

  @override
  ConsumerState<_ActiveBody> createState() => _ActiveBodyState();
}

class _ActiveBodyState extends ConsumerState<_ActiveBody> {
  late int _secondsLeft;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _secondsLeft = widget.token.expiresIn;
    _startTimer();
  }

  @override
  void didUpdateWidget(_ActiveBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.token.rideToken != widget.token.rideToken) {
      _timer?.cancel();
      _secondsLeft = widget.token.expiresIn;
      _startTimer();
    }
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _secondsLeft--);
      if (_secondsLeft <= 0) {
        _timer?.cancel();
        ref.read(rideTokenNotifierProvider.notifier).markExpired();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final fraction = _secondsLeft / widget.token.expiresIn;
    final isUrgent = _secondsLeft <= 10;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'Show this at the dock scanner',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          // QR code — encodes the raw JWT string
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: colorScheme.shadow.withOpacity(0.12),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            padding: const EdgeInsets.all(16),
            child: QrImageView(
              data: widget.token.rideToken,
              version: QrVersions.auto,
              size: 240,
              backgroundColor: Colors.white,
              errorCorrectionLevel: QrErrorCorrectLevel.M,
            ),
          ),
          const SizedBox(height: 32),
          // Countdown ring
          Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(
                width: 80,
                height: 80,
                child: CircularProgressIndicator(
                  value: fraction.clamp(0.0, 1.0),
                  strokeWidth: 6,
                  backgroundColor: colorScheme.surfaceContainerHighest,
                  color: isUrgent ? colorScheme.error : colorScheme.primary,
                ),
              ),
              Text(
                '$_secondsLeft',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: isUrgent
                          ? colorScheme.error
                          : colorScheme.onSurface,
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            isUrgent ? 'Expiring soon!' : 'Seconds remaining',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: isUrgent ? colorScheme.error : colorScheme.outline,
                ),
          ),
          const SizedBox(height: 32),
          Text(
            'One-time use · 30 second window',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: colorScheme.outlineVariant,
                ),
          ),
        ],
      ),
    );
  }
}

// ── Sub-states ─────────────────────────────────────────────────────────────────

class _LoadingBody extends StatelessWidget {
  const _LoadingBody();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Preparing your QR code…'),
        ],
      ),
    );
  }
}

class _ExpiredBody extends StatelessWidget {
  const _ExpiredBody({required this.onRegenerate});

  final VoidCallback onRegenerate;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.timer_off_outlined,
                size: 64, color: colorScheme.error),
            const SizedBox(height: 16),
            Text(
              'QR Code Expired',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'The 30 second window has passed. Generate a new code.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: colorScheme.outline,
                  ),
            ),
            const SizedBox(height: 32),
            FilledButton.icon(
              icon: const Icon(Icons.qr_code_2),
              label: const Text('Generate New Code'),
              onPressed: onRegenerate,
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorBody extends StatelessWidget {
  const _ErrorBody({
    required this.message,
    required this.onRetry,
    this.code,
  });

  final String message;
  final String? code;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    // RIDE_INVALID_STATE after dock validation — ride is active, no more QR.
    final isTerminal = code == 'RIDE_INVALID_STATE';

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isTerminal
                  ? Icons.electric_scooter_rounded
                  : Icons.error_outline,
              size: 64,
              color: isTerminal ? colorScheme.primary : colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              isTerminal ? 'Ride in Progress' : 'Something went wrong',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              isTerminal
                  ? 'Your scooter has been unlocked. Enjoy your ride!'
                  : message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: colorScheme.outline,
                  ),
            ),
            if (!isTerminal) ...[
              const SizedBox(height: 32),
              FilledButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Try Again'),
                onPressed: onRetry,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
