class User {
  const User({
    required this.id,
    required this.phoneNumber,
    required this.role,
    required this.createdAt,
    this.name,
  });

  final String id;
  final String phoneNumber;
  final String? name;
  final String role;
  final DateTime createdAt;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as String,
        phoneNumber: json['phone_number'] as String,
        name: json['name'] as String?,
        role: json['role'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  User copyWith({String? name}) => User(
        id: id,
        phoneNumber: phoneNumber,
        name: name ?? this.name,
        role: role,
        createdAt: createdAt,
      );
}