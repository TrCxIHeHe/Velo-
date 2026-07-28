import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';

abstract interface class RideRepository {
  Future<Ride> getRide(String id);
  Future<Ride?> getActiveRide();
  Future<RideToken> requestToken(String dockId);
  Future<Ride> endRide(String rideId, String dockId);
}
