import 'package:scooter/features/ride/domain/models/ride_token.dart';

abstract interface class RideRepository {
  /// POST /ride/request — creates a ride with status ASSIGNED.
  /// Raises ApiException with code RIDE_ALREADY_ACTIVE if one exists.
  Future<void> requestRide();

  /// POST /ride/token — issues a 30s HMAC-signed one-time QR token.
  /// Requires an ASSIGNED ride to exist for the current user.
  Future<RideToken> issueToken();
}
