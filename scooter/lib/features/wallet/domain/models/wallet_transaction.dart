enum WalletTransactionType {
  credit,
  debit;

  static WalletTransactionType fromJson(String value) => switch (value) {
        'CREDIT' => WalletTransactionType.credit,
        'DEBIT' => WalletTransactionType.debit,
        _ => WalletTransactionType.debit,
      };
}

enum WalletTransactionSource {
  topup,
  rideFare,
  refund,
  adminAdjustment,
  unknown;

  static WalletTransactionSource fromJson(String value) => switch (value) {
        'TOPUP' => WalletTransactionSource.topup,
        'RIDE_FARE' => WalletTransactionSource.rideFare,
        'REFUND' => WalletTransactionSource.refund,
        'ADMIN_ADJUSTMENT' => WalletTransactionSource.adminAdjustment,
        _ => WalletTransactionSource.unknown,
      };
}

class WalletTransaction {
  const WalletTransaction({
    required this.id,
    required this.type,
    required this.source,
    required this.amount,
    required this.balanceAfter,
    required this.createdAt,
    this.referenceId,
    this.note,
  });

  final String id;
  final WalletTransactionType type;
  final WalletTransactionSource source;
  final double amount;
  final double balanceAfter;
  final String? referenceId;
  final String? note;
  final DateTime createdAt;

  factory WalletTransaction.fromJson(Map<String, dynamic> json) => WalletTransaction(
        id: json['id'] as String,
        type: WalletTransactionType.fromJson(json['type'] as String),
        source: WalletTransactionSource.fromJson(json['source'] as String),
        amount: (json['amount'] as num).toDouble(),
        balanceAfter: (json['balance_after'] as num).toDouble(),
        referenceId: json['reference_id'] as String?,
        note: json['note'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class TransactionPage {
  const TransactionPage({required this.items, required this.total});

  final List<WalletTransaction> items;
  final int total;

  factory TransactionPage.fromJson(Map<String, dynamic> json) => TransactionPage(
        items: (json['items'] as List)
            .map((e) => WalletTransaction.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int,
      );
}
