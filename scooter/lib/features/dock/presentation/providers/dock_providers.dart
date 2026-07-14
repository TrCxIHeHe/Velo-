import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/dock/data/dock_remote_datasource.dart';
import 'package:scooter/features/dock/data/dock_repository_impl.dart';
import 'package:scooter/features/dock/domain/dock_repository.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_state.dart';

final Provider<DockRemoteDataSource> dockDataSourceProvider =
    Provider<DockRemoteDataSource>(
  (ref) => DockRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<DockRepository> dockRepositoryProvider =
    Provider<DockRepository>(
  (ref) => DockRepositoryImpl(ref.watch(dockDataSourceProvider)),
);

class DockNotifier extends StateNotifier<DockState> {
  DockNotifier(this._repo) : super(const DockInitial());

  final DockRepository _repo;

  Future<void> load() async {
    state = const DockLoading();
    try {
      final docks = await _repo.listDocks();
      state = DockLoaded(docks);
    } catch (e) {
      state = DockError(e.toString());
    }
  }

  Future<void> refresh() => load();

  /// Fetches individual dock detail (includes available_slots).
  /// Returns updated Dock or null on error.
  Future<Dock?> fetchDockDetail(String dockId) async {
    try {
      return await _repo.getDock(dockId);
    } catch (_) {
      return null;
    }
  }
}

final StateNotifierProvider<DockNotifier, DockState> dockNotifierProvider =
    StateNotifierProvider<DockNotifier, DockState>(
  (ref) => DockNotifier(ref.watch(dockRepositoryProvider)),
);
