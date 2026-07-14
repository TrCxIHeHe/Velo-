import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/ride/data/ride_remote_datasource.dart';
import 'package:scooter/features/ride/data/ride_repository_impl.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';

final Provider<RideRemoteDataSource> rideDataSourceProvider =
    Provider<RideRemoteDataSource>(
  (ref) => RideRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<RideRepository> rideRepositoryProvider =
    Provider<RideRepository>(
  (ref) => RideRepositoryImpl(ref.watch(rideDataSourceProvider)),
);
