import 'package:scooter/core/utils/server_time.dart';

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
    this.pricingStrategy,
  });

  final String id;
  final String userId;
  final String? vehicleId;
  final String startDockId;
  final String? endDockId;
  final String status;

  /// All timestamps are UTC instants (see [parseServerTimestamp]).
  final DateTime? startedAt;
  final DateTime? endedAt;
  final int? durationSeconds;

  /// Final fare as persisted by the server — never computed on the client.
  final double? fareAmount;
  final String fareCurrency;
  final String? pricingStrategy;
  final DateTime createdAt;

  bool get isActive => status == 'ACTIVE';

  factory Ride.fromJson(Map<String, dynamic> json) => Ride(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        vehicleId: json['vehicle_id'] as String?,
        startDockId: json['start_dock_id'] as String,
        endDockId: json['end_dock_id'] as String?,
        status: json['status'] as String,
        startedAt: parseServerTimestampOrNull(json['started_at']),
        endedAt: parseServerTimestampOrNull(json['ended_at']),
        durationSeconds: (json['duration_seconds'] as num?)?.toInt(),
        fareAmount: (json['fare_amount'] as num?)?.toDouble(),
        fareCurrency: json['fare_currency'] as String,
        pricingStrategy: json['pricing_strategy'] as String?,
        createdAt: parseServerTimestamp(json['created_at'] as String),
      );
}
