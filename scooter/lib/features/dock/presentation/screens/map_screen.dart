import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/dock/presentation/providers/dock_state.dart';

// Default map center — Bengaluru. Overridden to dock centroid once loaded.
// Top-level so both _MapScreenState and _MapBody can reference it.
const LatLng _kDefaultCenter = LatLng(12.9716, 77.5946);
const double _kDefaultZoom = 14.0;

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  final MapController _mapController = MapController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(dockNotifierProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dockNotifierProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dock Map'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(dockNotifierProvider.notifier).refresh(),
          ),
        ],
      ),
      body: switch (state) {
        DockInitial() || DockLoading() => const _LoadingOverlay(),
        DockError(:final message) => _ErrorBody(
            message: message,
            onRetry: () =>
                ref.read(dockNotifierProvider.notifier).refresh(),
          ),
        DockLoaded(:final docks) => _MapBody(
            docks: docks,
            mapController: _mapController,
            onDockTap: (dock) => _showDockDetail(context, ref, dock),
          ),
      },
    );
  }

  Future<void> _showDockDetail(
    BuildContext context,
    WidgetRef ref,
    Dock dock,
  ) async {
    // Fetch detail (includes available_slots) then show bottom sheet.
    final detail =
        await ref.read(dockNotifierProvider.notifier).fetchDockDetail(dock.id);
    if (!context.mounted) return;
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => _DockDetailSheet(dock: detail ?? dock),
    );
  }
}

class _MapBody extends StatelessWidget {
  const _MapBody({
    required this.docks,
    required this.mapController,
    required this.onDockTap,
  });

  final List<Dock> docks;
  final MapController mapController;
  final void Function(Dock) onDockTap;

  @override
  Widget build(BuildContext context) {
    // Center map on centroid of all docks if available, else default.
    final center = _centroid(docks) ?? _kDefaultCenter;

    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: center,
        initialZoom: _kDefaultZoom,
      ),
      children: [
        // OpenStreetMap tile layer — matches architecture doc (free, no billing)
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.scooter.app',
        ),
        MarkerLayer(
          markers: docks.map((dock) => _buildMarker(context, dock)).toList(),
        ),
      ],
    );
  }

  Marker _buildMarker(BuildContext context, Dock dock) {
    final colorScheme = Theme.of(context).colorScheme;
    final isActive = dock.isActive;

    return Marker(
      point: LatLng(dock.latitude, dock.longitude),
      width: 80,
      height: 80,
      child: GestureDetector(
        onTap: () => onDockTap(dock),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              decoration: BoxDecoration(
                color: isActive ? colorScheme.primary : colorScheme.outline,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.2),
                    blurRadius: 6,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              padding: const EdgeInsets.all(8),
              child: Icon(
                Icons.electric_scooter_rounded,
                color: isActive
                    ? colorScheme.onPrimary
                    : colorScheme.onSurface,
                size: 20,
              ),
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 4,
                  ),
                ],
              ),
              child: Text(
                dock.name.length > 10
                    ? '${dock.name.substring(0, 10)}…'
                    : dock.name,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontSize: 9,
                      fontWeight: FontWeight.w600,
                    ),
                maxLines: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }

  LatLng? _centroid(List<Dock> docks) {
    if (docks.isEmpty) return null;
    final lat = docks.map((d) => d.latitude).reduce((a, b) => a + b) /
        docks.length;
    final lng = docks.map((d) => d.longitude).reduce((a, b) => a + b) /
        docks.length;
    return LatLng(lat, lng);
  }
}

// ── Dock detail bottom sheet ───────────────────────────────────────────────────

class _DockDetailSheet extends StatelessWidget {
  const _DockDetailSheet({required this.dock});

  final Dock dock;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final availableSlots = dock.availableSlots;
    final statusColor = switch (dock.status) {
      'ACTIVE' => Colors.green.shade700,
      'OFFLINE' => colorScheme.error,
      _ => colorScheme.outline,
    };

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: colorScheme.outlineVariant,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: Text(
                  dock.name,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  dock.status,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: statusColor,
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (availableSlots != null) ...[
            _StatRow(
              icon: Icons.check_circle_outline,
              label: 'Available slots',
              value: '$availableSlots / ${dock.totalSlots}',
              valueColor:
                  availableSlots > 0 ? Colors.green.shade700 : colorScheme.error,
            ),
          ] else ...[
            _StatRow(
              icon: Icons.dock_rounded,
              label: 'Total slots',
              value: '${dock.totalSlots}',
            ),
          ],
          const SizedBox(height: 8),
          _StatRow(
            icon: Icons.location_on_outlined,
            label: 'Coordinates',
            value:
                '${dock.latitude.toStringAsFixed(5)}, ${dock.longitude.toStringAsFixed(5)}',
          ),
        ],
      ),
    );
  }
}

class _StatRow extends StatelessWidget {
  const _StatRow({
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 20, color: colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: colorScheme.outline,
                      ),
                ),
                Text(
                  value,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: valueColor,
                        fontWeight: FontWeight.w500,
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

// ── Loading / Error ────────────────────────────────────────────────────────────

class _LoadingOverlay extends StatelessWidget {
  const _LoadingOverlay();

  @override
  Widget build(BuildContext context) {
    return const Stack(
      children: [
        // Placeholder grey background while loading
        ColoredBox(color: Color(0xFFE8E8E8), child: SizedBox.expand()),
        Center(child: CircularProgressIndicator()),
      ],
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
            Icon(Icons.map_outlined,
                size: 48,
                color: Theme.of(context).colorScheme.error),
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