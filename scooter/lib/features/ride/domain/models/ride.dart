class Ride {
  const Ride({
    required this.id,
    required this.userId,
    required this.status,
    required this.createdAt,
    this.vehicleId,
    this.dockStartId,
    this.dockEndId,
    this.fare,
    this.startAt,
    this.endAt,
  });

  final String id;
  final String userId;
  final String? vehicleId;
  final String? dockStartId;
  final String? dockEndId;
  // ASSIGNED | UNLOCK_PENDING | ACTIVE | END_PENDING | COMPLETED | ...
  final String status;
  // null until Phase 4 fare calculation lands.
  final double? fare;
  final DateTime? startAt;
  final DateTime? endAt;
  final DateTime createdAt;

  factory Ride.fromJson(Map<String, dynamic> json) => Ride(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        vehicleId: json['vehicle_id'] as String?,
        dockStartId: json['dock_start_id'] as String?,
        dockEndId: json['dock_end_id'] as String?,
        status: json['status'] as String,
        fare: json['fare'] == null ? null : (json['fare'] as num).toDouble(),
        startAt: json['start_at'] == null
            ? null
            : DateTime.parse(json['start_at'] as String),
        endAt: json['end_at'] == null
            ? null
            : DateTime.parse(json['end_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  bool get isActive => status == 'ACTIVE';
  bool get isAwaitingUnlock =>
      status == 'ASSIGNED' || status == 'UNLOCK_PENDING';
  bool get isTerminal =>
      const {'COMPLETED', 'CANCELLED', 'FAILED', 'FORCE_TERMINATED'}
          .contains(status);
}
