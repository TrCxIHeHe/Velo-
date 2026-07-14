import 'package:scooter/features/dock/data/dock_remote_datasource.dart';
import 'package:scooter/features/dock/domain/dock_repository.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

class DockRepositoryImpl implements DockRepository {
  const DockRepositoryImpl(this._ds);

  final DockRemoteDataSource _ds;

  @override
  Future<List<Dock>> listDocks({int limit = 50, int offset = 0}) =>
      _ds.listDocks(limit: limit, offset: offset);

  @override
  Future<Dock> getDock(String dockId) => _ds.getDock(dockId);
}
