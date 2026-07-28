import 'package:scooter/features/ride/data/ride_remote_datasource.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';

class RideRepositoryImpl implements RideRepository {
  const RideRepositoryImpl(this._remote);

  final RideRemoteDataSource _remote;

  @override
  Future<Ride> getRide(String id) => _remote.getRide(id);

  @override
  Future<Ride?> getActiveRide() => _remote.getActiveRide();

  @override
  Future<RideToken> requestToken(String dockId) => _remote.requestToken(dockId);

  @override
  Future<Ride> endRide(String rideId, String dockId) => _remote.endRide(rideId, dockId);
}
