class WalletTransaction {
  const WalletTransaction({
    required this.id,
    required this.walletId,
    required this.type,
    required this.amount,
    required this.createdAt,
    this.referenceId,
  });

  final String id;
  final String walletId;
  // Backend values: CREDIT | DEBIT | REFUND
  final String type;
  final double amount;
  final String? referenceId;
  final DateTime createdAt;

  factory WalletTransaction.fromJson(Map<String, dynamic> json) =>
      WalletTransaction(
        id: json['id'] as String,
        walletId: json['wallet_id'] as String,
        type: json['type'] as String,
        amount: double.parse(json['amount'].toString()),
        referenceId: json['reference_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
