/// One line of the receipt breakdown.
class FareLineItem {
  const FareLineItem(this.label, this.amount);
  final String label;
  final double amount;
}

/// Presentation of a fare that the **server** already calculated and charged.
///
/// With the fixed dock-pair model the fare does not depend on duration, so
/// there is nothing to compute or reconcile here: the breakdown is a single
/// transparent line (the route) whose amount is exactly the persisted
/// `fare_amount`. Rides priced by another/legacy rule simply show "Ride fare".
class FareBreakdown {
  const FareBreakdown(this.lineItems, this.total);

  final List<FareLineItem> lineItems;
  final double total;

  static const String fixedDockPairStrategy = 'fixed_dock_pair';

  factory FareBreakdown.fromRide({
    required double fareAmount,
    String? pricingStrategy,
    String? originName,
    String? destinationName,
  }) {
    final isFixedPair = pricingStrategy == fixedDockPairStrategy;
    final label = !isFixedPair
        ? 'Ride fare'
        : (originName != null && destinationName != null)
            ? 'Fixed route fare · $originName → $destinationName'
            : 'Fixed route fare';
    return FareBreakdown([FareLineItem(label, fareAmount)], fareAmount);
  }
}
