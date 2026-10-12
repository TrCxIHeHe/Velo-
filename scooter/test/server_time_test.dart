import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/core/utils/server_time.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';

void main() {
  // 10:00:00 UTC == 15:30:00 IST
  final instant = DateTime.utc(2026, 10, 11, 10, 0, 0);

  group('parseServerTimestamp', () {
    test('explicit UTC (Z) is parsed as that exact instant', () {
      final t = parseServerTimestamp('2026-10-11T10:00:00Z');
      expect(t, instant);
      expect(t.isUtc, isTrue);
    });

    test('explicit offset (IST +05:30) is converted to the same UTC instant', () {
      expect(parseServerTimestamp('2026-10-11T15:30:00+05:30'), instant);
      expect(parseServerTimestamp('2026-10-11T15:30:00+0530'), instant);
      expect(parseServerTimestamp('2026-10-11T10:00:00+00:00'), instant);
    });

    test('legacy zone-less value is UTC, not device-local time', () {
      final t = parseServerTimestamp('2026-10-11T10:00:00.123456');
      expect(t.isUtc, isTrue);
      expect(t, DateTime.utc(2026, 10, 11, 10, 0, 0, 123, 456));
    });

    test('legacy space-separated zone-less value is UTC', () {
      expect(parseServerTimestamp('2026-10-11 10:00:00'), instant);
    });

    test('the date part "-10-11" is never mistaken for a zone offset', () {
      expect(parseServerTimestamp('2026-10-11T10:00:00'), instant);
    });

    test('microsecond precision from the backend is accepted', () {
      final t = parseServerTimestamp('2026-10-11T10:15:30.123456Z');
      expect(t.microsecond, 456);
      expect(t.millisecond, 123);
    });
  });

  group('elapsed duration', () {
    test('equals now - started_at regardless of how the start was encoded', () {
      final now = DateTime.utc(2026, 10, 11, 10, 12, 34);
      for (final raw in [
        '2026-10-11T10:00:00Z', // UTC
        '2026-10-11T15:30:00+05:30', // IST
        '2026-10-11T10:00:00', // legacy naive UTC
      ]) {
        final d = elapsedSince(parseServerTimestamp(raw), now);
        expect(d, const Duration(minutes: 12, seconds: 34), reason: raw);
        expect(formatElapsed(d), '12:34');
      }
    });

    test('now given in a non-UTC zone (IST wall clock) gives the same elapsed time', () {
      // 15:42:34 IST is 10:12:34 UTC; represent "now" as a *local-looking* DateTime
      // built from the same instant — elapsedSince normalises both to UTC.
      final nowIst = DateTime.utc(2026, 10, 11, 10, 12, 34).toLocal();
      expect(elapsedSince(instant, nowIst), const Duration(minutes: 12, seconds: 34));
    });

    test('never negative under small clock skew', () {
      expect(elapsedSince(instant, instant.subtract(const Duration(seconds: 3))), Duration.zero);
    });

    test('formatElapsed switches to h:mm:ss after an hour', () {
      expect(formatElapsed(const Duration(seconds: 5)), '00:05');
      expect(formatElapsed(const Duration(minutes: 59, seconds: 59)), '59:59');
      expect(formatElapsed(const Duration(hours: 1, minutes: 2, seconds: 3)), '1:02:03');
    });
  });

  group('Ride.fromJson', () {
    Map<String, dynamic> json({required String startedAt}) => {
          'id': 'r',
          'user_id': 'u',
          'vehicle_id': null,
          'start_dock_id': 'A',
          'end_dock_id': null,
          'status': 'ACTIVE',
          'started_at': startedAt,
          'ended_at': null,
          'duration_seconds': null,
          'fare_amount': null,
          'fare_currency': 'INR',
          'created_at': '2026-10-11T09:00:00',
        };

    test('explicit and legacy timestamps yield the same start instant', () {
      final a = Ride.fromJson(json(startedAt: '2026-10-11T10:00:00Z'));
      final b = Ride.fromJson(json(startedAt: '2026-10-11T10:00:00'));
      expect(a.startedAt, instant);
      expect(b.startedAt, instant);
      expect(b.createdAt, DateTime.utc(2026, 10, 11, 9));
    });

    test('parses server fare and strategy without recomputing', () {
      final r = Ride.fromJson({
        ...json(startedAt: '2026-10-11T10:00:00Z'),
        'status': 'COMPLETED',
        'fare_amount': 20.5,
        'pricing_strategy': 'fixed_dock_pair',
        'duration_seconds': 754,
      });
      expect(r.fareAmount, 20.5);
      expect(r.pricingStrategy, 'fixed_dock_pair');
      expect(r.durationSeconds, 754);
      expect(r.isActive, isFalse);
    });
  });
}
