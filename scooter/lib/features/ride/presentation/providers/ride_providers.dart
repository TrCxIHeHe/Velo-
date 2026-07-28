import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/ride/data/ride_remote_datasource.dart';
import 'package:scooter/features/ride/data/ride_repository_impl.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';

final Provider<RideRemoteDataSource> rideDataSourceProvider = Provider<RideRemoteDataSource>(
  (ref) => RideRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<RideRepository> rideRepositoryProvider = Provider<RideRepository>(
  (ref) => RideRepositoryImpl(ref.watch(rideDataSourceProvider)),
);

final AutoDisposeFutureProviderFamily<Ride, String> rideDetailProvider =
    FutureProvider.autoDispose.family<Ride, String>(
  (ref, rideId) => ref.watch(rideRepositoryProvider).getRide(rideId),
);

/// The caller's current in-progress ride, if any. Re-fetch with
/// `ref.invalidate(activeRideProvider)` — used both for polling (QR unlock
/// screen, waiting for dock hardware to confirm) and for refreshing after
/// an action (ending a ride).
final AutoDisposeFutureProvider<Ride?> activeRideProvider = FutureProvider.autoDispose<Ride?>(
  (ref) => ref.watch(rideRepositoryProvider).getActiveRide(),
);
