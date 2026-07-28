import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/dock/data/dock_remote_datasource.dart';
import 'package:scooter/features/dock/data/dock_repository_impl.dart';
import 'package:scooter/features/dock/domain/dock_repository.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';

final Provider<DockRemoteDataSource> dockDataSourceProvider = Provider<DockRemoteDataSource>(
  (ref) => DockRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<DockRepository> dockRepositoryProvider = Provider<DockRepository>(
  (ref) => DockRepositoryImpl(ref.watch(dockDataSourceProvider)),
);

final AutoDisposeFutureProvider<List<Dock>> dockListProvider =
    FutureProvider.autoDispose<List<Dock>>(
  (ref) => ref.watch(dockRepositoryProvider).listDocks(),
);
