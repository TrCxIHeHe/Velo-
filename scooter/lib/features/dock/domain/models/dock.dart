class Dock {
  const Dock({
    required this.id,
    required this.name,
    required this.latitude,
    required this.longitude,
    required this.totalSlots,
    required this.status,
    required this.createdAt,
    this.availableSlots,
  });

  final String id;
  final String name;
  final double latitude;
  final double longitude;
  final int totalSlots;
  final String status; // ACTIVE | OFFLINE | MAINTENANCE
  final DateTime createdAt;
  // Only populated when fetched individually via GET /docks/{id}
  final int? availableSlots;

  factory Dock.fromJson(Map<String, dynamic> json) => Dock(
        id: json['id'] as String,
        name: json['name'] as String,
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
        totalSlots: json['total_slots'] as int,
        status: json['status'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        // available_slots only present in DockWithSlotsResponse (single dock)
        availableSlots: json['available_slots'] as int?,
      );

  bool get isActive => status == 'ACTIVE';
}
