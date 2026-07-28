class RazorpayOrder {
  const RazorpayOrder({
    required this.orderId,
    required this.amount,
    required this.currency,
    required this.keyId,
  });

  final String orderId;
  final double amount;
  final String currency;
  final String keyId;

  factory RazorpayOrder.fromJson(Map<String, dynamic> json) => RazorpayOrder(
        orderId: json['order_id'] as String,
        amount: (json['amount'] as num).toDouble(),
        currency: json['currency'] as String,
        keyId: json['key_id'] as String,
      );
}
