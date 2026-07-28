import 'package:scooter/features/dock/data/dock_remote_datasource.dart';
import 'package:scooter/features/dock/domain/dock_repository.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

class DockRepositoryImpl implements DockRepository {
  const DockRepositoryImpl(this._remote);

  final DockRemoteDataSource _remote;

  @override
  Future<List<Dock>> listDocks() => _remote.listDocks();

  @override
  Future<Dock> getDock(String dockId) => _remote.getDock(dockId);
}
