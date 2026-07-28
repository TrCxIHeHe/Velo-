class Wallet {
  const Wallet({
    required this.id,
    required this.userId,
    required this.balance,
    required this.currency,
    required this.updatedAt,
  });

  final String id;
  final String userId;
  final double balance;
  final String currency;
  final DateTime updatedAt;

  factory Wallet.fromJson(Map<String, dynamic> json) => Wallet(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        balance: (json['balance'] as num).toDouble(),
        currency: json['currency'] as String,
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}
