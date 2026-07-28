import 'package:flutter/material.dart';
import 'package:scooter/core/widgets/app_button.dart';

/// Loading / Empty / Error / Offline placeholder (Figma `3:40`) —
/// emoji icon, 13/semibold title, 11/muted subtitle, optional retry.
class StateView extends StatelessWidget {
  const StateView.loading({super.key, this.title = 'Loading', this.subtitle = 'Fetching your data…'})
      : icon = '⏳',
        onRetry = null;

  const StateView.empty({
    super.key,
    this.title = 'Nothing here yet',
    this.subtitle = '',
  })  : icon = '📭',
        onRetry = null;

  const StateView.error({
    super.key,
    this.title = 'Something went wrong',
    this.subtitle = 'Please try again.',
    this.onRetry,
  }) : icon = '⚠️';

  const StateView.offline({
    super.key,
    this.title = 'Offline',
    this.subtitle = 'Check your connection.',
    this.onRetry,
  }) : icon = '📡';

  final String icon;
  final String title;
  final String subtitle;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).hintColor;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(icon, style: const TextStyle(fontSize: 28)),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            if (subtitle.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(fontSize: 12, color: muted),
                textAlign: TextAlign.center,
              ),
            ],
            if (onRetry != null) ...[
              const SizedBox(height: 20),
              SizedBox(
                width: 160,
                child: SecondaryButton(label: 'Retry', onPressed: onRetry),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
