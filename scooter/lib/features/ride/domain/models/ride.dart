class Ride {
  const Ride({
    required this.id,
    required this.userId,
    required this.startDockId,
    required this.status,
    required this.fareCurrency,
    required this.createdAt,
    this.vehicleId,
    this.endDockId,
    this.startedAt,
    this.endedAt,
    this.durationSeconds,
    this.fareAmount,
  });

  final String id;
  final String userId;
  final String? vehicleId;
  final String startDockId;
  final String? endDockId;
  final String status;
  final DateTime? startedAt;
  final DateTime? endedAt;
  final int? durationSeconds;
  final double? fareAmount;
  final String fareCurrency;
  final DateTime createdAt;

  factory Ride.fromJson(Map<String, dynamic> json) => Ride(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        vehicleId: json['vehicle_id'] as String?,
        startDockId: json['start_dock_id'] as String,
        endDockId: json['end_dock_id'] as String?,
        status: json['status'] as String,
        startedAt: json['started_at'] != null ? DateTime.parse(json['started_at'] as String) : null,
        endedAt: json['ended_at'] != null ? DateTime.parse(json['ended_at'] as String) : null,
        durationSeconds: json['duration_seconds'] as int?,
        fareAmount: (json['fare_amount'] as num?)?.toDouble(),
        fareCurrency: json['fare_currency'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
