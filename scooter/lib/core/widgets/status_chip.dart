import 'package:flutter/material.dart';
import 'package:scooter/core/theme/app_semantic_colors.dart';

enum StatusChipVariant { success, offline, error }

/// Chips / Status pill (Figma `3:20`) — radius 999, 12h/6v padding.
class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.label, required this.variant});

  final String label;
  final StatusChipVariant variant;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final semantic = context.semanticColors;

    final (Color bg, Color fg) = switch (variant) {
      StatusChipVariant.success => (semantic.chipSuccessBg, semantic.stateSuccess),
      StatusChipVariant.offline => (semantic.chipOfflineBg, semantic.textMuted),
      StatusChipVariant.error => (semantic.chipErrorBg, scheme.error),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(
        label,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: fg),
      ),
    );
  }
}
