class Dock {
  const Dock({
    required this.id,
    required this.name,
    required this.locationLat,
    required this.locationLng,
    required this.totalSlots,
    required this.availableSlots,
    required this.isActive,
    this.address,
  });

  final String id;
  final String name;
  final double locationLat;
  final double locationLng;
  final String? address;
  final int totalSlots;
  final int availableSlots;
  final bool isActive;

  factory Dock.fromJson(Map<String, dynamic> json) => Dock(
        id: json['id'] as String,
        name: json['name'] as String,
        locationLat: (json['location_lat'] as num).toDouble(),
        locationLng: (json['location_lng'] as num).toDouble(),
        address: json['address'] as String?,
        totalSlots: json['total_slots'] as int,
        availableSlots: json['available_slots'] as int,
        isActive: json['is_active'] as bool,
      );
}
