abstract final class StorageKeys {
  static const String accessToken = 'access_token';
  static const String refreshToken = 'refresh_token';
  // Persists the ride_id of an in-progress ride so the tracking screen can
  // resume after an app restart. No backend endpoint exists to look up a
  // user's active ride by user_id alone — this is the only recovery path.
  static const String activeRideId = 'active_ride_id';
}
