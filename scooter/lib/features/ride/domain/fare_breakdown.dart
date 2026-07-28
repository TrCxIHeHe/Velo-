import 'dart:math';

const double kFarePerMinute = 2.0;
const double kMinimumFare = 5.0;

class FareLineItem {
  const FareLineItem(this.label, this.amount);
  final String label;
  final double amount;
}

/// Client-side presentation of the backend's fare rule
/// (`backend/app/ride/service.py:_calculate_fare` — ₹2/minute, ₹5 minimum,
/// billed minutes rounded up). Mirrors that formula exactly so the
/// breakdown always reconciles to the ride's actual `fare_amount`; if a
/// ride ever doesn't match (e.g. a future pricing change), it falls back
/// to a single line item showing the true total rather than a breakdown
/// that doesn't add up.
class FareBreakdown {
  const FareBreakdown(this.lineItems, this.total);

  final List<FareLineItem> lineItems;
  final double total;

  static int billedMinutes(int durationSeconds) => (durationSeconds / 60).ceil();

  static double computeFare(int durationSeconds) {
    final minutes = billedMinutes(durationSeconds);
    final fare = max(minutes * kFarePerMinute, kMinimumFare);
    return double.parse(fare.toStringAsFixed(2));
  }

  factory FareBreakdown.fromRide({required int durationSeconds, required double fareAmount}) {
    final minutes = billedMinutes(durationSeconds);
    final computed = computeFare(durationSeconds);

    if ((computed - fareAmount).abs() > 0.01) {
      return FareBreakdown([FareLineItem('Ride fare', fareAmount)], fareAmount);
    }

    if (minutes * kFarePerMinute <= kMinimumFare) {
      return FareBreakdown([FareLineItem('Minimum fare', fareAmount)], fareAmount);
    }

    return FareBreakdown(
      [FareLineItem('Ride fare ($minutes min × ₹${kFarePerMinute.toStringAsFixed(2)})', fareAmount)],
      fareAmount,
    );
  }
}
