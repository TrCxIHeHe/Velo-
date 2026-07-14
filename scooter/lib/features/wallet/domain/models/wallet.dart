class Wallet {
  const Wallet({
    required this.id,
    required this.userId,
    required this.currency,
    required this.balance,
    required this.createdAt,
  });

  final String id;
  final String userId;
  final String currency;
  final double balance;
  final DateTime createdAt;

  factory Wallet.fromJson(Map<String, dynamic> json) => Wallet(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        currency: json['currency'] as String,
        // balance comes as Decimal from Python — arrives as string or num
        balance: double.parse(json['balance'].toString()),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
