import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:scooter/core/constants/storage_keys.dart';

class SecureStorageService {
  const SecureStorageService(this._storage);

  final FlutterSecureStorage _storage;

  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
  }) async {
    await Future.wait([
      _storage.write(key: StorageKeys.accessToken, value: accessToken),
      _storage.write(key: StorageKeys.refreshToken, value: refreshToken),
    ]);
  }

  Future<String?> getAccessToken() =>
      _storage.read(key: StorageKeys.accessToken);

  Future<String?> getRefreshToken() =>
      _storage.read(key: StorageKeys.refreshToken);

  Future<void> clearSession() async {
    await Future.wait([
      _storage.delete(key: StorageKeys.accessToken),
      _storage.delete(key: StorageKeys.refreshToken),
      _storage.delete(key: StorageKeys.activeRideId),
    ]);
  }

  // ── Active ride resumption ──────────────────────────────────────────────
  // No GET /ride/active endpoint exists. This is the only way the tracking
  // screen can recover a ride_id after the app is killed and relaunched.

  Future<void> saveActiveRideId(String rideId) =>
      _storage.write(key: StorageKeys.activeRideId, value: rideId);

  Future<String?> getActiveRideId() =>
      _storage.read(key: StorageKeys.activeRideId);

  Future<void> clearActiveRideId() =>
      _storage.delete(key: StorageKeys.activeRideId);
}
