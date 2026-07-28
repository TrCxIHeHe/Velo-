import 'dart:math';

/// Generates a random RFC-4122 v4-formatted UUID string using a
/// cryptographically secure RNG. No third-party `uuid` package needed —
/// this is only used as an opaque, locally-generated device identifier
/// (see SecureStorageService.getOrCreateDeviceId), not for anything that
/// needs strict UUID spec compliance.
String generateDeviceId() {
  final rand = Random.secure();
  final bytes = List<int>.generate(16, (_) => rand.nextInt(256));

  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10xx

  String hex(int start, int end) =>
      bytes.sublist(start, end).map((b) => b.toRadixString(16).padLeft(2, '0')).join();

  return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
}
