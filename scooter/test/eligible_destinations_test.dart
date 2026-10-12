import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/features/dock/domain/eligible_destinations.dart';

import 'support/fakes.dart';

void main() {
  test('keeps only active docks with a free slot, excluding the origin, sorted by name', () {
    final result = eligibleDestinations([
      dock('A', name: 'Origin', free: 4),
      dock('B', name: 'Zeta', free: 1),
      dock('C', name: 'Alpha', free: 2),
      dock('D', name: 'Full', free: 0),
      dock('E', name: 'Closed', free: 3, active: false),
    ], originDockId: 'A');

    expect(result.map((d) => d.name), ['Alpha', 'Zeta']);
  });

  test('returns an empty list when nothing is eligible', () {
    expect(eligibleDestinations([dock('A'), dock('B', free: 0)], originDockId: 'A'), isEmpty);
  });
}
