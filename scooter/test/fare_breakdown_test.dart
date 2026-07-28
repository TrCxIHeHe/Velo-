import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/features/ride/domain/fare_breakdown.dart';

void main() {
  group('FareBreakdown.computeFare', () {
    test('rounds up partial minutes and applies ₹2/minute', () {
      // 90 seconds -> ceil(1.5) = 2 minutes -> ₹4.00, but below minimum.
      expect(FareBreakdown.computeFare(90), 5.0);
    });

    test('applies the minimum fare for very short rides', () {
      expect(FareBreakdown.computeFare(30), 5.0);
      expect(FareBreakdown.billedMinutes(30), 1);
    });

    test('charges per full billed minute once above the minimum', () {
      // 601 seconds -> ceil(10.02) = 11 minutes -> ₹22.00
      expect(FareBreakdown.computeFare(601), 22.0);
      expect(FareBreakdown.billedMinutes(601), 11);
    });

    test('exact minute boundary does not round up an extra minute', () {
      // 600 seconds -> exactly 10 minutes -> ₹20.00
      expect(FareBreakdown.computeFare(600), 20.0);
      expect(FareBreakdown.billedMinutes(600), 10);
    });
  });

  group('FareBreakdown.fromRide', () {
    test('line items always sum to the ride fare total', () {
      for (final duration in [10, 30, 60, 90, 150, 300, 601, 1800]) {
        final fare = FareBreakdown.computeFare(duration);
        final breakdown = FareBreakdown.fromRide(durationSeconds: duration, fareAmount: fare);
        final sum = breakdown.lineItems.fold<double>(0, (acc, item) => acc + item.amount);
        expect(sum, closeTo(breakdown.total, 0.001), reason: 'duration=$duration');
        expect(breakdown.total, fare);
      }
    });

    test('labels the minimum-fare case distinctly from the per-minute case', () {
      final short = FareBreakdown.fromRide(durationSeconds: 30, fareAmount: 5.0);
      expect(short.lineItems.single.label, 'Minimum fare');

      final long = FareBreakdown.fromRide(durationSeconds: 601, fareAmount: 22.0);
      expect(long.lineItems.single.label, contains('11 min'));
    });

    test('falls back to a single true-total line item on a mismatched fare', () {
      // Simulates a ride whose stored fare doesn't match the current formula
      // (e.g. a historical pricing change) — must never show a breakdown
      // that silently doesn't add up to the real total.
      final breakdown = FareBreakdown.fromRide(durationSeconds: 601, fareAmount: 99.0);
      expect(breakdown.lineItems.single.amount, 99.0);
      expect(breakdown.total, 99.0);
    });
  });
}
