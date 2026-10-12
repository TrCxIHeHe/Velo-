import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/features/ride/presentation/screens/ride_receipt_screen.dart';

import 'support/fakes.dart';

Future<void> _pump(WidgetTester tester, Ride ride) async {
  final rides = FakeRideRepository()..rideById = ride;
  final docks = FakeDockRepository(docks: [dock('A', name: 'Origin'), dock('B', name: 'Bravo')]);
  final router = GoRouter(
    initialLocation: '/rides/ride-1/receipt',
    routes: [
      GoRoute(path: '/rides/:id/receipt', builder: (_, s) => RideReceiptScreen(rideId: s.pathParameters['id']!)),
      GoRoute(path: '/home', builder: (_, __) => const Scaffold(body: Text('HOME'))),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        rideRepositoryProvider.overrideWithValue(rides),
        dockRepositoryProvider.overrideWithValue(docks),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows the server fare, route breakdown and recorded duration', (tester) async {
    await _pump(tester, completedRide(fare: 20.5, duration: 754));

    expect(find.text('₹20.50'), findsWidgets);                    // exactly the persisted fare
    expect(find.text('Fixed route fare · Origin → Bravo'), findsOneWidget);
    expect(find.text('12:34'), findsOneWidget);                   // server duration, not recomputed
    expect(find.text('Total charged'), findsOneWidget);
  });

  testWidgets('end time is shown in the device-local zone', (tester) async {
    final ride = completedRide();
    await _pump(tester, ride);
    final expected = DateFormat('d MMM yyyy, HH:mm').format(ride.endedAt!.toLocal());
    expect(find.text(expected), findsOneWidget);
  });

  testWidgets('a legacy ride without a pricing strategy shows a plain "Ride fare"', (tester) async {
    await _pump(tester, completedRide(strategy: null, fare: 22));
    expect(find.text('Ride fare'), findsOneWidget);
    expect(find.text('₹22.00'), findsWidgets);
  });

  testWidgets('Done and system back both return Home', (tester) async {
    await _pump(tester, completedRide());
    await tester.tap(find.byKey(const Key('receipt-done')));
    await tester.pumpAndSettle();
    expect(find.text('HOME'), findsOneWidget);

    await _pump(tester, completedRide());
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('HOME'), findsOneWidget);
  });
}
