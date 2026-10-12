/// Server-calculated estimate for ending a ride at one destination dock.
/// Display only: the final charge is recomputed by the server on completion.
class FareQuote {
  const FareQuote({
    required this.rideId,
    required this.originDockId,
    required this.destinationDockId,
    required this.fareAmount,
    required this.currency,
    required this.pricingStrategy,
    this.walletBalance,
    this.sufficientBalance,
  });

  final String rideId;
  final String originDockId;
  final String destinationDockId;
  final double fareAmount;
  final String currency;
  final String pricingStrategy;
  final double? walletBalance;
  final bool? sufficientBalance;

  factory FareQuote.fromJson(Map<String, dynamic> json) => FareQuote(
        rideId: json['ride_id'] as String,
        originDockId: json['origin_dock_id'] as String,
        destinationDockId: json['destination_dock_id'] as String,
        fareAmount: (json['fare_amount'] as num).toDouble(),
        currency: json['currency'] as String,
        pricingStrategy: json['pricing_strategy'] as String,
        walletBalance: (json['wallet_balance'] as num?)?.toDouble(),
        sufficientBalance: json['sufficient_balance'] as bool?,
      );
}
