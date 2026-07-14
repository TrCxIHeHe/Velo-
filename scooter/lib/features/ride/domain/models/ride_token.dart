class RideToken {
  const RideToken({
    required this.rideToken,
    required this.expiresIn,
    required this.expiresAt,
  });

  /// The JWT string — encode this directly as the QR code content.
  final String rideToken;

  /// Seconds until expiry — use for countdown timer initial value.
  final int expiresIn;

  /// Absolute UTC expiry — source of truth for expiry check.
  final DateTime expiresAt;

  factory RideToken.fromJson(Map<String, dynamic> json) => RideToken(
        rideToken: json['ride_token'] as String,
        expiresIn: json['expires_in'] as int,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );

  bool get isExpired => DateTime.now().toUtc().isAfter(expiresAt);
}
