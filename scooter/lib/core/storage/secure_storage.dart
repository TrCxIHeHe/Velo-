import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:scooter/core/constants/storage_keys.dart';
import 'package:scooter/core/storage/device_id.dart';

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
    ]);
  }

  Future<void> saveThemeMode(String mode) =>
      _storage.write(key: StorageKeys.themeMode, value: mode);

  Future<String?> getThemeMode() => _storage.read(key: StorageKeys.themeMode);

  /// Returns this install's stable device identifier, generating and
  /// persisting one on first call. Sent as `X-Device-Id` on every request
  /// (see dio_client.dart) and used by the backend to bind refresh tokens
  /// to the device that requested them.
  Future<String> getOrCreateDeviceId() async {
    final existing = await _storage.read(key: StorageKeys.deviceId);
    if (existing != null) return existing;
    final id = generateDeviceId();
    await _storage.write(key: StorageKeys.deviceId, value: id);
    return id;
  }
}