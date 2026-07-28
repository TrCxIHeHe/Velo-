import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:scooter/core/constants/api_constants.dart';
import 'package:scooter/core/network/token_interceptor.dart';
import 'package:scooter/core/storage/secure_storage.dart';

/// SHA-256 fingerprint (hex, colon-free) of the production TLS leaf
/// certificate to pin against. Unset by default — nothing is deployed
/// yet, so there's no real cert to pin against. Set via
/// `--dart-define=CERT_PIN_SHA256=HEX` in the release build once a
/// production backend is live; get the hash with:
///   openssl s_client -connect api.velo.example:443 < /dev/null 2> /dev/null \
///     | openssl x509 -noout -fingerprint -sha256
const String _certPinSha256 = String.fromEnvironment('CERT_PIN_SHA256');

Dio createDio(SecureStorageService storage, void Function() onSessionExpired) {
  final dio = Dio(
    BaseOptions(
      baseUrl: ApiConstants.baseUrl,
      connectTimeout: ApiConstants.connectTimeout,
      receiveTimeout: ApiConstants.receiveTimeout,
      headers: {'Content-Type': 'application/json'},
    ),
  );

  if (_certPinSha256.isNotEmpty && dio.httpClientAdapter is IOHttpClientAdapter) {
    (dio.httpClientAdapter as IOHttpClientAdapter).createHttpClient = () {
      final client = HttpClient();
      // Reached only when the platform's default trust evaluation didn't
      // already accept the cert (or to enforce our stricter check on top
      // of it); compare the presented leaf cert's SHA-256 fingerprint
      // against the pinned value and accept only on an exact match.
      client.badCertificateCallback = (cert, host, port) {
        final fingerprint = sha256.convert(cert.der).toString();
        return fingerprint == _certPinSha256.toLowerCase();
      };
      return client;
    };
  }

  dio.interceptors.add(
    TokenInterceptor(
      storage: storage,
      dio: dio,
      onSessionExpired: onSessionExpired,
    ),
  );
  return dio;
}
