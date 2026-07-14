import 'package:scooter/features/dock/domain/models/dock.dart';

abstract interface class DockRepository {
  /// GET /api/v1/docks — returns DockResponse list (total_slots, no available_slots).
  Future<List<Dock>> listDocks({int limit = 50, int offset = 0});

  /// GET /api/v1/docks/{id} — returns DockWithSlotsResponse (includes available_slots).
  Future<Dock> getDock(String dockId);
}
