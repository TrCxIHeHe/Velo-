import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

/// What the ride map shows. These are *dock* locations only.
class RideMapData {
  const RideMapData({this.origin, this.destinations = const [], this.selected});

  final Dock? origin;
  final List<Dock> destinations;
  final Dock? selected;
}

const LatLng _fallbackCenter = LatLng(12.9716, 77.5946);

/// Origin and eligible destination docks on the app's existing OSM map.
///
/// The backend does not provide a live scooter position, so this never draws
/// one: the caption makes clear that markers are dock locations.
class RideMap extends StatefulWidget {
  const RideMap({super.key, required this.data, this.onSelectDock});

  final RideMapData data;
  final ValueChanged<Dock>? onSelectDock;

  @override
  State<RideMap> createState() => _RideMapState();
}

class _RideMapState extends State<RideMap> {
  final MapController _controller = MapController();
  bool _ready = false;

  List<LatLng> _points(RideMapData d) => [
        if (d.origin != null) LatLng(d.origin!.locationLat, d.origin!.locationLng),
        if (d.selected != null)
          LatLng(d.selected!.locationLat, d.selected!.locationLng)
        else
          for (final dock in d.destinations) LatLng(dock.locationLat, dock.locationLng),
      ];

  void _fit() {
    if (!_ready) return;
    final pts = _points(widget.data);
    if (pts.isEmpty) return;
    if (pts.length == 1) {
      _controller.move(pts.first, 15);
    } else {
      _controller.fitCamera(
        CameraFit.bounds(bounds: LatLngBounds.fromPoints(pts), padding: const EdgeInsets.all(56), maxZoom: 16),
      );
    }
  }

  @override
  void didUpdateWidget(RideMap old) {
    super.didUpdateWidget(old);
    final changed = old.data.selected?.id != widget.data.selected?.id ||
        old.data.origin?.id != widget.data.origin?.id ||
        old.data.destinations.length != widget.data.destinations.length;
    if (changed) WidgetsBinding.instance.addPostFrameCallback((_) => _fit());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final d = widget.data;
    final pts = _points(d);

    Marker dockMarker(Dock dock, {required Color color, required IconData icon, required String label, double size = 40}) {
      return Marker(
        point: LatLng(dock.locationLat, dock.locationLng),
        width: size,
        height: size,
        child: Semantics(
          label: '$label: ${dock.name}',
          button: widget.onSelectDock != null && label != 'Start dock',
          child: GestureDetector(
            onTap: label == 'Start dock' ? null : () => widget.onSelectDock?.call(dock),
            child: Container(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color,
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
              ),
              child: Icon(icon, color: Colors.white, size: size * 0.5),
            ),
          ),
        ),
      );
    }

    return Stack(
      children: [
        FlutterMap(
          mapController: _controller,
          options: MapOptions(
            initialCenter: pts.isNotEmpty ? pts.first : _fallbackCenter,
            initialZoom: 14,
            onMapReady: () {
              _ready = true;
              _fit();
            },
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.velo.scooter',
            ),
            MarkerLayer(
              markers: [
                for (final dock in d.destinations)
                  if (dock.id != d.selected?.id)
                    dockMarker(dock, color: Colors.grey.shade600, icon: Icons.local_parking, label: 'Destination dock'),
                if (d.selected != null)
                  dockMarker(d.selected!,
                      color: scheme.primary, icon: Icons.check, label: 'Selected destination', size: 48),
                if (d.origin != null)
                  dockMarker(d.origin!, color: Colors.green.shade700, icon: Icons.flag, label: 'Start dock'),
              ],
            ),
          ],
        ),
        Positioned(
          left: 12,
          top: 12,
          right: 12,
          child: Align(
            alignment: Alignment.centerLeft,
            child: Container(
              key: const Key('map-caption'),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor.withValues(alpha: 0.92),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Dock locations · live scooter position isn\'t tracked',
                style: TextStyle(fontSize: 11, color: Theme.of(context).hintColor),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
