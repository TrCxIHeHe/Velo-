import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/core/utils/server_time.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/domain/models/fare_quote.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/presentation/providers/ride_providers.dart';
import 'package:scooter/features/ride/presentation/screens/ride_tracking_screen.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';

import 'support/fakes.dart';

class _Harness {
  _Harness({Ride? ride, bool standalone = true})
      : rides = FakeRideRepository(active: ride ?? activeRide()),
        docks = FakeDockRepository(docks: [
          dock('A', name: 'Origin'),
          dock('B', name: 'Bravo'),
          dock('C', name: 'Charlie'),
        ]),
        _standalone = standalone;

  final FakeRideRepository rides;
  final FakeDockRepository docks;
  final bool _standalone;
  DateTime now = DateTime.utc(2026, 10, 11, 10, 12, 34);

  Future<void> pump(WidgetTester tester) async {
    final router = GoRouter(
      initialLocation: '/ride/active',
      routes: [
        GoRoute(
          path: '/ride/active',
          builder: (_, __) => RideTrackingScreen(
            standalone: _standalone,
            now: () => now,
            mapBuilder: (_, data, onSelect) => Container(key: const Key('fake-map')),
          ),
        ),
        GoRoute(path: '/home', builder: (_, __) => const Scaffold(body: Text('HOME'))),
        GoRoute(
          path: '/rides/:id/receipt',
          builder: (_, s) => Scaffold(body: Text('RECEIPT ${s.pathParameters['id']}')),
        ),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          rideRepositoryProvider.overrideWithValue(rides),
          dockRepositoryProvider.overrideWithValue(docks),
          walletRepositoryProvider.overrideWithValue(FakeWalletRepository()),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> choose(WidgetTester tester, String dockId) async {
    await tester.tap(find.byKey(const Key('destination-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(Key('dock-option-$dockId')));
    // Not pumpAndSettle: a pending quote shows a spinner that animates forever.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }
}

bool _endEnabled(WidgetTester tester) =>
    tester.widget<PrimaryButton>(find.byKey(const Key('end-ride-button'))).onPressed != null;

void main() {
  group('duration', () {
    testWidgets('is derived from started_at and ticks every second', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      expect(find.text('12:34'), findsOneWidget);

      h.now = h.now.add(const Duration(seconds: 1));
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('12:35'), findsOneWidget);
      expect(find.text('12:34'), findsNothing);
    });

    testWidgets('is correct for a start timestamp sent in IST and as legacy naive UTC', (tester) async {
      for (final raw in ['2026-10-11T15:30:00+05:30', '2026-10-11T10:00:00']) {
        final h = _Harness(ride: activeRide(startedAt: parseServerTimestamp(raw)));
        await h.pump(tester);
        expect(find.text('12:34'), findsOneWidget, reason: raw);
        await tester.pumpWidget(const SizedBox());
      }
    });
  });

  group('fare estimate', () {
    testWidgets('is hidden and End Ride disabled until a destination is chosen', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      expect(find.byKey(const Key('fare-hint')), findsOneWidget);
      expect(find.byKey(const Key('fare-amount')), findsNothing);
      expect(_endEnabled(tester), isFalse);
      expect(h.rides.quoteRequests, isEmpty);
    });

    testWidgets('selecting a destination requests that exact pair and shows the server fare', (tester) async {
      final h = _Harness();
      h.rides.quotes['B'] = () => quote('B', 20);
      await h.pump(tester);
      await h.choose(tester, 'B');

      expect(h.rides.quoteRequests, ['B']);
      expect(find.byKey(const Key('fare-amount')), findsOneWidget);
      expect(find.text('₹20.00'), findsOneWidget);
      expect(find.text('Bravo'), findsWidgets);
      expect(_endEnabled(tester), isTrue);
    });

    testWidgets('shows a loading state and no fare while the quote is pending', (tester) async {
      final h = _Harness();
      final gate = Completer<FareQuote>();
      h.rides.quotes['B'] = () => gate.future;
      await h.pump(tester);
      await h.choose(tester, 'B');

      expect(find.byKey(const Key('fare-loading')), findsOneWidget);
      expect(find.byKey(const Key('fare-amount')), findsNothing);
      expect(_endEnabled(tester), isFalse);

      gate.complete(quote('B', 20));
      await tester.pump();
      await tester.pumpAndSettle();
      expect(find.text('₹20.00'), findsOneWidget);
    });

    testWidgets('changing destination clears the previous fare immediately', (tester) async {
      final h = _Harness();
      final gateC = Completer<FareQuote>();
      h.rides.quotes['B'] = () => quote('B', 20);
      h.rides.quotes['C'] = () => gateC.future;
      await h.pump(tester);

      await h.choose(tester, 'B');
      expect(find.text('₹20.00'), findsOneWidget);

      await h.choose(tester, 'C');
      expect(find.text('₹20.00'), findsNothing); // stale fare gone while C loads
      expect(find.byKey(const Key('fare-loading')), findsOneWidget);
      expect(_endEnabled(tester), isFalse);
      expect(h.rides.quoteRequests, ['B', 'C']);

      gateC.complete(quote('C', 35.5));
      await tester.pump();
      await tester.pumpAndSettle();
      expect(find.text('₹35.50'), findsOneWidget);
      expect(_endEnabled(tester), isTrue);
    });

    testWidgets('quote failure shows an error, keeps End disabled, and Retry recovers', (tester) async {
      final h = _Harness();
      h.rides.quotes['B'] = () =>
          throw const ApiException(code: 'FARE_NOT_CONFIGURED', message: 'No active fare is configured.');
      await h.pump(tester);
      await h.choose(tester, 'B');

      expect(find.byKey(const Key('fare-error')), findsOneWidget);
      expect(find.textContaining('No active fare'), findsOneWidget);
      expect(find.byKey(const Key('fare-amount')), findsNothing);
      expect(_endEnabled(tester), isFalse);

      h.rides.quotes['B'] = () => quote('B', 20);
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.text('₹20.00'), findsOneWidget);
    });

    testWidgets('warns when the wallet may not cover the fare', (tester) async {
      final h = _Harness();
      h.rides.quotes['B'] = () => quote('B', 20, sufficient: false);
      await h.pump(tester);
      await h.choose(tester, 'B');
      expect(find.byKey(const Key('fare-balance-warning')), findsOneWidget);
    });
  });

  group('ending the ride', () {
    Future<_Harness> ready(WidgetTester tester) async {
      final h = _Harness();
      h.rides.quotes['B'] = () => quote('B', 20);
      h.rides.quotes['C'] = () => quote('C', 35);
      await h.pump(tester);
      await h.choose(tester, 'B');
      return h;
    }

    testWidgets('asks for confirmation; declining ends nothing', (tester) async {
      final h = await ready(tester);
      await tester.tap(find.byKey(const Key('end-ride-button')));
      await tester.pumpAndSettle();
      expect(find.text('End ride?'), findsOneWidget);
      expect(find.textContaining('₹20.00'), findsWidgets);

      await tester.tap(find.byKey(const Key('end-cancel')));
      await tester.pumpAndSettle();

      expect(h.rides.endCalls, isEmpty);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
      expect(_endEnabled(tester), isTrue);
    });

    testWidgets('navigates to the receipt only after the backend confirms', (tester) async {
      final h = await ready(tester);
      final gate = Completer<Ride>();
      h.rides.onEnd = (_, __) => gate.future;

      await tester.tap(find.byKey(const Key('end-ride-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('end-confirm')));
      await tester.pump();

      // in flight: still on the ride screen, button busy and not tappable again
      expect(find.textContaining('RECEIPT'), findsNothing);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
      expect(tester.widget<PrimaryButton>(find.byKey(const Key('end-ride-button'))).loading, isTrue);
      expect(_endEnabled(tester), isFalse);

      h.rides.active = null; // server now has no active ride
      gate.complete(completedRide());
      await tester.pumpAndSettle();

      expect(h.rides.endCalls, [('ride-1', 'B')]); // exactly one submission
      expect(find.text('RECEIPT ride-1'), findsOneWidget);
    });

    testWidgets('failure keeps the screen and destination and lets the user retry', (tester) async {
      final h = await ready(tester);
      var attempt = 0;
      h.rides.onEnd = (_, __) async {
        attempt++;
        if (attempt == 1) {
          throw const ApiException(code: 'WALLET_INSUFFICIENT_BALANCE', message: 'Wallet balance is insufficient.');
        }
        return completedRide();
      };

      await tester.tap(find.byKey(const Key('end-ride-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('end-confirm')));
      await tester.pumpAndSettle();

      expect(find.text('Wallet balance is insufficient.'), findsOneWidget); // snackbar
      expect(find.textContaining('RECEIPT'), findsNothing);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
      expect(find.text('₹20.00'), findsOneWidget); // destination + quote retained
      expect(_endEnabled(tester), isTrue);

      // let the floating snackbar time out so it cannot cover the button
      await tester.pump(const Duration(seconds: 6));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('end-ride-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('end-confirm')));
      await tester.pumpAndSettle();

      expect(h.rides.endCalls, hasLength(2));
      expect(find.text('RECEIPT ride-1'), findsOneWidget);
    });

    testWidgets('a destination that filled up is dropped so another can be chosen', (tester) async {
      final h = await ready(tester);
      h.rides.onEnd = (_, __) async =>
          throw const ApiException(code: 'DOCK_FULL', message: 'This dock has no available slots.');
      final before = h.docks.listCalls;

      await tester.tap(find.byKey(const Key('end-ride-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('end-confirm')));
      await tester.pumpAndSettle();

      expect(find.text('This dock has no available slots.'), findsOneWidget);
      expect(find.byKey(const Key('fare-hint')), findsOneWidget); // selection cleared
      expect(_endEnabled(tester), isFalse);
      expect(h.docks.listCalls, greaterThan(before)); // availability refreshed
      expect(find.textContaining('RECEIPT'), findsNothing);

      // choose another dock -> fresh quote
      await tester.pump(const Duration(seconds: 6));
      await tester.pumpAndSettle();
      await h.choose(tester, 'C');
      expect(find.text('₹35.00'), findsOneWidget);
    });
  });

  group('refresh and state', () {
    testWidgets('a background refresh keeps the ride on screen (no spinner)', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      expect(find.text('12:34'), findsOneWidget);

      h.rides.activeGate = Completer<Ride?>();
      ProviderScope.containerOf(tester.element(find.byType(RideTrackingScreen)))
          .invalidate(activeRideProvider);
      await tester.pump();

      expect(find.text('Loading your ride…'), findsNothing);
      expect(find.byKey(const Key('ride-duration')), findsOneWidget);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);

      h.rides.activeGate!.complete(h.rides.active);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
    });

    testWidgets('a failed refresh keeps the last known ride and shows a retry banner', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      h.rides.activeError = const NetworkException();
      ProviderScope.containerOf(tester.element(find.byType(RideTrackingScreen)))
          .invalidate(activeRideProvider);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('stale-banner')), findsOneWidget);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);

      h.rides.activeError = null;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('stale-banner')), findsNothing);
    });

    testWidgets('a ride that ended elsewhere turns into the empty state', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      h.rides.active = null;
      ProviderScope.containerOf(tester.element(find.byType(RideTrackingScreen)))
          .invalidate(activeRideProvider);
      await tester.pumpAndSettle();

      expect(find.text('No active ride'), findsOneWidget);
      expect(find.byKey(const Key('end-ride-button')), findsNothing);
    });

    testWidgets('first load shows a loading state, then the ride', (tester) async {
      final h = _Harness();
      h.rides.activeGate = Completer<Ride?>();
      await h.pump(tester);
      expect(find.text('Loading your ride…'), findsOneWidget);

      h.rides.activeGate!.complete(activeRide());
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
    });

    testWidgets('reconciles with the backend periodically', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      final before = h.rides.activeCalls;
      await tester.pump(const Duration(seconds: 16));
      await tester.pump();
      expect(h.rides.activeCalls, greaterThan(before));
    });
  });

  group('navigation', () {
    testWidgets('visible back button returns Home without ending or cancelling the ride', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      await tester.tap(find.byKey(const Key('ride-back')));
      await tester.pumpAndSettle();

      expect(find.text('HOME'), findsOneWidget);
      expect(h.rides.endCalls, isEmpty);
      expect(h.rides.cancelCalls, isEmpty);
      expect(h.rides.active, isNotNull);
    });

    testWidgets('Android system back also returns Home', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();

      expect(find.text('HOME'), findsOneWidget);
      expect(h.rides.endCalls, isEmpty);
      expect(h.rides.cancelCalls, isEmpty);
    });

    testWidgets('as a Ride tab (not standalone) there is no back button', (tester) async {
      final h = _Harness(standalone: false);
      await h.pump(tester);
      expect(find.byKey(const Key('ride-back')), findsNothing);
      expect(find.byKey(const Key('ride-status')), findsOneWidget);
    });
  });
}
