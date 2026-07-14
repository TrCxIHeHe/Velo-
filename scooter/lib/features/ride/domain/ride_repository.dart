import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';

// NOTE — missing backend endpoint:
// There is no GET /ride/active (or equivalent "my current ride") route.
// The only way this client ever learns a ride_id is the 201 response body
// of POST /ride/request. If that ride_id is lost (app reinstalled, storage
// cleared) while a ride is still ASSIGNED/ACTIVE server-side, there is no
// way to recover it — POST /ride/request will 409 RIDE_ALREADY_ACTIVE with
// no ride_id in the error body. Flagging this rather than inventing a call.
abstract interface class RideRepository {
  /// POST /ride/request — creates a ride with status ASSIGNED, returns it.
  /// Raises ApiException code RIDE_ALREADY_ACTIVE if one already exists —
  /// caller must fall back to fetching the existing active ride.
  Future<Ride> requestRide();

  /// POST /ride/token — issues a 30s HMAC-signed one-time QR token.
  /// Requires an ASSIGNED ride to exist for the current user.
  Future<RideToken> issueToken();

  /// GET /ride/{ride_id} — full ride record.
  Future<Ride> getRide(String rideId);

  /// GET /ride/status/{ride_id} — id + status only, cheap for polling.
  Future<String> getRideStatus(String rideId);
}
