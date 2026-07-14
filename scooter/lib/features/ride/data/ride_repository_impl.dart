import 'package:scooter/features/ride/data/ride_remote_datasource.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';

class RideRepositoryImpl implements RideRepository {
  const RideRepositoryImpl(this._ds);

  final RideRemoteDataSource _ds;

  @override
  Future<Ride> requestRide() => _ds.requestRide();

  @override
  Future<RideToken> issueToken() => _ds.issueToken();

  @override
  Future<Ride> getRide(String rideId) => _ds.getRide(rideId);

  @override
  Future<String> getRideStatus(String rideId) => _ds.getRideStatus(rideId);
}
