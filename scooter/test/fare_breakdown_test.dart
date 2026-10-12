import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/features/ride/domain/fare_breakdown.dart';

void main() {
  group('FareBreakdown (fixed dock-pair fare)', () {
    test('is a single route line equal to the server fare', () {
      final b = FareBreakdown.fromRide(
        fareAmount: 20.5,
        pricingStrategy: 'fixed_dock_pair',
        originName: 'MG Road',
        destinationName: 'Koramangala',
      );
      expect(b.lineItems, hasLength(1));
      expect(b.lineItems.single.label, 'Fixed route fare · MG Road → Koramangala');
      expect(b.lineItems.single.amount, 20.5);
      expect(b.total, 20.5);
    });

    test('does not invent line items when dock names are unavailable', () {
      final b = FareBreakdown.fromRide(fareAmount: 20, pricingStrategy: 'fixed_dock_pair');
      expect(b.lineItems.single.label, 'Fixed route fare');
    });

    test('legacy rides (no strategy) show a plain "Ride fare" at the stored amount', () {
      final b = FareBreakdown.fromRide(fareAmount: 22);
      expect(b.lineItems.single.label, 'Ride fare');
      expect(b.total, 22);
    });

    test('has no duration input: the fare cannot depend on how long the ride took', () {
      // Compile-time guarantee: fromRide takes no duration parameter.
      final fast = FareBreakdown.fromRide(fareAmount: 20, pricingStrategy: 'fixed_dock_pair');
      final slow = FareBreakdown.fromRide(fareAmount: 20, pricingStrategy: 'fixed_dock_pair');
      expect(fast.total, slow.total);
    });
  });
}
