import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:scooter/core/theme/app_semantic_colors.dart';
import 'package:scooter/core/widgets/state_view.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/dock/presentation/widgets/dock_detail_sheet.dart';

const LatLng _fallbackCenter = LatLng(12.9716, 77.5946); // Bengaluru — used when there are no docks yet

class MapScreen extends ConsumerWidget {
  const MapScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docksAsync = ref.watch(dockListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dock Map'),
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
        data: (docks) => _Map(docks: docks),
      ),
    );
  }
}

class _Map extends StatelessWidget {
  const _Map({required this.docks});
  final List<Dock> docks;

  @override
  Widget build(BuildContext context) {
    final center = docks.isNotEmpty ? LatLng(docks.first.locationLat, docks.first.locationLng) : _fallbackCenter;
    final scheme = Theme.of(context).colorScheme;
    final semantic = context.semanticColors;

    return FlutterMap(
      options: MapOptions(initialCenter: center, initialZoom: 14),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.velo.scooter',
        ),
        MarkerLayer(
          markers: [
            for (final dock in docks)
              Marker(
                point: LatLng(dock.locationLat, dock.locationLng),
                width: 40,
                height: 40,
                child: GestureDetector(
                  onTap: () => showDockDetailSheet(context, dock),
                  child: Container(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: dock.availableSlots > 0 ? scheme.primary : semantic.textMuted,
                      border: Border.all(color: Colors.white, width: 2),
                      boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
                    ),
                    child: const Icon(Icons.pedal_bike, color: Colors.white, size: 20),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
