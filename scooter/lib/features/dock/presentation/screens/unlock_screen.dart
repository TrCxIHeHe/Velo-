import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/core/widgets/status_chip.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/router/app_router.dart';

/// Dock picker — an alternate entry point into the QR unlock flow,
/// distinct from tapping a marker on the Map tab (matches the Figma bottom
/// nav's separate "Unlock" destination).
class UnlockScreen extends ConsumerWidget {
  const UnlockScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docksAsync = ref.watch(dockListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Unlock a Scooter'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(dockListProvider),
          ),
        ],
      ),
      body: docksAsync.when(
        loading: () => const StateView.loading(),
        error: (e, _) => StateView.error(
          subtitle: e.toString(),
          onRetry: () => ref.invalidate(dockListProvider),
        ),
        data: (docks) {
          if (docks.isEmpty) {
            return const StateView.empty(subtitle: 'No docks nearby yet');
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(dockListProvider),
            child: ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: docks.length,
              separatorBuilder: (_, __) => const Divider(),
              itemBuilder: (context, i) {
                final dock = docks[i];
                final canUnlock = dock.isActive && dock.availableSlots > 0;
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.pedal_bike_outlined),
                  title: Text(dock.name),
                  subtitle: dock.address != null ? Text(dock.address!) : null,
                  trailing: canUnlock
                      ? StatusChip(
                          label: '${dock.availableSlots} free',
                          variant: StatusChipVariant.success,
                        )
                      : const StatusChip(label: 'Full', variant: StatusChipVariant.error),
                  onTap: canUnlock
                      ? () => context.pushNamed(
                            AppRoutes.qrUnlock,
                            pathParameters: {'dockId': dock.id},
                          )
                      : null,
                );
              },
            ),
          );
        },
      ),
    );
  }
}
