class RideToken {
  const RideToken({
    required this.rideToken,
    required this.rideId,
    required this.expiresInSeconds,
  });

  final String rideToken;
  final String rideId;
  final int expiresInSeconds;

  factory RideToken.fromJson(Map<String, dynamic> json) => RideToken(
        rideToken: json['ride_token'] as String,
        rideId: json['ride_id'] as String,
        expiresInSeconds: json['expires_in_seconds'] as int,
      );
}
