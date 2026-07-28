import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/status_chip.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/router/app_router.dart';

/// Bottom Sheet — Dock Detail (Figma `3:59`): drag handle, dock name,
/// slots-available chip, "Unlock a Scooter" CTA.
Future<void> showDockDetailSheet(BuildContext context, Dock dock) {
  return showModalBottomSheet<void>(
    context: context,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (ctx) => Padding(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Theme.of(ctx).dividerColor,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(dock.name, style: Theme.of(ctx).textTheme.headlineSmall?.copyWith(fontSize: 18)),
          const SizedBox(height: 12),
          StatusChip(
            label: dock.availableSlots > 0
                ? '${dock.availableSlots} of ${dock.totalSlots} slots available'
                : 'No slots available',
            variant: dock.availableSlots > 0 ? StatusChipVariant.success : StatusChipVariant.error,
          ),
          const SizedBox(height: 24),
          PrimaryButton(
            label: 'Unlock a Scooter',
            onPressed: dock.isActive && dock.availableSlots > 0
                ? () {
                    Navigator.of(ctx).pop();
                    context.pushNamed(AppRoutes.qrUnlock, pathParameters: {'dockId': dock.id});
                  }
                : null,
          ),
        ],
      ),
    ),
  );
}
