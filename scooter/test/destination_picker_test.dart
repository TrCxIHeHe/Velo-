import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/dock/presentation/providers/dock_providers.dart';
import 'package:scooter/features/ride/presentation/widgets/destination_picker_sheet.dart';

import 'support/fakes.dart';

Future<void> _open(WidgetTester tester, FakeDockRepository repo, void Function(Dock?) onResult) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [dockRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        home: Consumer(
          builder: (context, ref, _) => Scaffold(
            body: ElevatedButton(
              key: const Key('open'),
              onPressed: () async =>
                  onResult(await DestinationPickerSheet.show(context, ref, originDockId: 'A')),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.byKey(const Key('open')));
}

void main() {
  testWidgets('shows a loading state and then the docks - it does not spin forever', (tester) async {
    final repo = FakeDockRepository()..gate = Completer<List<Dock>>();
    await _open(tester, repo, (_) {});
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byKey(const Key('picker-loading')), findsOneWidget);

    repo.gate!.complete([dock('A', name: 'Origin'), dock('B', name: 'Bravo', free: 2)]);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('picker-loading')), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('Bravo'), findsOneWidget);
    expect(find.textContaining('2 free slots'), findsOneWidget);
  });

  testWidgets('lists only active docks with free slots and never the origin', (tester) async {
    final repo = FakeDockRepository(docks: [
      dock('A', name: 'Origin', free: 5),
      dock('B', name: 'Bravo', free: 1),
      dock('C', name: 'Full', free: 0),
      dock('D', name: 'Closed', free: 4, active: false),
    ]);
    await _open(tester, repo, (_) {});
    await tester.pumpAndSettle();

    expect(find.text('Bravo'), findsOneWidget);
    expect(find.textContaining('1 free slot of'), findsOneWidget); // singular
    expect(find.text('Origin'), findsNothing);
    expect(find.text('Full'), findsNothing);
    expect(find.text('Closed'), findsNothing);
  });

  testWidgets('shows an error with Retry and recovers when the retry succeeds', (tester) async {
    final repo = FakeDockRepository()..failWith = Exception('boom');
    await _open(tester, repo, (_) {});
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('picker-error')), findsOneWidget);
    expect(find.textContaining('boom'), findsOneWidget);

    repo
      ..failWith = null
      ..docks = [dock('A'), dock('B', name: 'Bravo')];
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('picker-error')), findsNothing);
    expect(find.text('Bravo'), findsOneWidget);
  });

  testWidgets('shows an explicit empty state when no destination is eligible', (tester) async {
    final repo = FakeDockRepository(docks: [dock('A'), dock('B', free: 0)]);
    await _open(tester, repo, (_) {});
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('picker-empty')), findsOneWidget);
    expect(find.text('No docks available'), findsOneWidget);

    // Refresh re-queries and picks up a newly freed slot.
    repo.docks = [dock('A'), dock('B', name: 'Bravo', free: 1)];
    await tester.tap(find.text('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('Bravo'), findsOneWidget);
  });

  testWidgets('tapping a dock closes the sheet and returns it', (tester) async {
    Dock? chosen;
    final repo = FakeDockRepository(docks: [dock('A'), dock('B', name: 'Bravo')]);
    await _open(tester, repo, (d) => chosen = d);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('dock-option-B')));
    await tester.pumpAndSettle();

    expect(chosen?.id, 'B');
    expect(find.byType(DestinationPickerSheet), findsNothing);
  });

  testWidgets('re-fetches docks every time it is opened (fresh availability)', (tester) async {
    final repo = FakeDockRepository(docks: [dock('A'), dock('B', name: 'Bravo')]);
    await _open(tester, repo, (_) {});
    await tester.pumpAndSettle();
    final first = repo.listCalls;
    expect(first, greaterThanOrEqualTo(1));

    await tester.tapAt(const Offset(5, 5)); // dismiss the sheet
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open')));
    await tester.pumpAndSettle();

    expect(repo.listCalls, greaterThan(first));
  });
}
