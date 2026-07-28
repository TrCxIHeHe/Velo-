import 'package:scooter/features/dock/domain/models/dock.dart';

abstract interface class DockRepository {
  Future<List<Dock>> listDocks();
  Future<Dock> getDock(String dockId);
}
