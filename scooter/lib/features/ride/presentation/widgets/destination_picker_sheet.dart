import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/features/dock/domain/eligible_destinations.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';

/// Bottom sheet listing the docks a ride can be ended at.
///
/// It *watches* [dockListProvider] itself, so it reacts to loading → data /
/// error → retry. (The previous implementation read the provider once before
/// opening the sheet and rendered that captured `AsyncValue`, which never
/// changes — hence the endless spinner.)
class DestinationPickerSheet extends ConsumerWidget {
  const DestinationPickerSheet({super.key, required this.originDockId, this.selectedDockId});

  final String originDockId;
  final String? selectedDockId;

  /// Opens the sheet and resolves with the chosen dock (or null if dismissed).
  /// Forces a fresh docks fetch so slot availability is current.
  static Future<Dock?> show(
    BuildContext context,
    WidgetRef ref, {
    required String originDockId,
    String? selectedDockId,
  }) {
    ref.invalidate(dockListProvider);
    return showModalBottomSheet<Dock>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => DestinationPickerSheet(originDockId: originDockId, selectedDockId: selectedDockId),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docksAsync = ref.watch(dockListProvider);
    final maxHeight = MediaQuery.sizeOf(context).height * 0.7;

    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: maxHeight),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Return to which dock?', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'Only docks with a free slot are listed.',
              style: TextStyle(fontSize: 12, color: Theme.of(context).hintColor),
            ),
            const SizedBox(height: 12),
            if (docksAsync.isLoading && docksAsync.hasValue) const LinearProgressIndicator(minHeight: 2),
            Flexible(child: _content(context, ref, docksAsync)),
          ],
        ),
      ),
    );
  }

  Widget _content(BuildContext context, WidgetRef ref, AsyncValue<List<Dock>> docksAsync) {
    if (docksAsync.hasError && !docksAsync.isLoading) {
      return _Message(
        key: const Key('picker-error'),
        icon: Icons.error_outline,
        title: "Couldn't load docks",
        subtitle: docksAsync.error.toString(),
        onRetry: () => ref.invalidate(dockListProvider),
      );
    }
    if (!docksAsync.hasValue) {
      return const Padding(
        key: Key('picker-loading'),
        padding: EdgeInsets.all(32),
        child: Center(child: CircularProgressIndicator()),
      );
    }

    final eligible = eligibleDestinations(docksAsync.requireValue, originDockId: originDockId);
    if (eligible.isEmpty) {
      return _Message(
        key: const Key('picker-empty'),
        icon: Icons.local_parking,
        title: 'No docks available',
        subtitle: 'Every other dock is full or closed right now. Try again in a moment.',
        onRetry: () => ref.invalidate(dockListProvider),
        retryLabel: 'Refresh',
      );
    }

    return ListView.separated(
      key: const Key('picker-list'),
      shrinkWrap: true,
      itemCount: eligible.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final dock = eligible[i];
        final selected = dock.id == selectedDockId;
        final slots = dock.availableSlots;
        return ListTile(
          key: Key('dock-option-${dock.id}'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.pedal_bike_outlined),
          title: Text(dock.name),
          subtitle: Text(
            [
              '$slots free slot${slots == 1 ? '' : 's'} of ${dock.totalSlots}',
              if (dock.address != null && dock.address!.isNotEmpty) dock.address!,
            ].join(' · '),
          ),
          trailing: selected ? Icon(Icons.check_circle, color: Theme.of(context).colorScheme.primary) : null,
          onTap: () => Navigator.of(context).pop(dock),
        );
      },
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onRetry,
    this.retryLabel = 'Retry',
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onRetry;
  final String retryLabel;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 32, color: Theme.of(context).hintColor),
          const SizedBox(height: 8),
          Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: Theme.of(context).hintColor),
          ),
          const SizedBox(height: 16),
          SizedBox(width: 160, child: SecondaryButton(label: retryLabel, onPressed: onRetry)),
        ],
      ),
    );
  }
}
