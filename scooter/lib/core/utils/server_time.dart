/// Backend timestamp contract: ISO-8601 UTC with a `Z` suffix.
///
/// Older rows/responses may still carry a zone-less value such as
/// `2026-10-11T10:15:30.123456`. Those are UTC too (the DB stores naive UTC),
/// but `DateTime.parse` would read them as the *device's local time* and shift
/// every duration by the UTC offset (+5h30m on an IST phone). This parser
/// always returns a UTC `DateTime`.
final RegExp _zoneSuffix = RegExp(r'(?:[zZ]|[+-]\d{2}(?::?\d{2})?)$');

DateTime parseServerTimestamp(String raw) {
  var s = raw.trim();
  if (!s.contains('T')) {
    // "2026-10-11 10:15:30" style
    s = s.replaceFirst(' ', 'T');
  }
  final tIndex = s.indexOf('T');
  if (tIndex >= 0) {
    // Only look for a zone in the time part, never in the date's "-10-11".
    final timePart = s.substring(tIndex + 1);
    if (!_zoneSuffix.hasMatch(timePart)) {
      s = '${s}Z';
    }
  }
  return DateTime.parse(s).toUtc();
}

DateTime? parseServerTimestampOrNull(Object? raw) =>
    raw == null ? null : parseServerTimestamp(raw as String);

/// Elapsed time between a UTC start and "now", never negative (small clock
/// skew between phone and server must not render "-00:03").
Duration elapsedSince(DateTime startedAt, DateTime now) {
  final d = now.toUtc().difference(startedAt.toUtc());
  return d.isNegative ? Duration.zero : d;
}

/// `mm:ss`, or `h:mm:ss` from one hour on.
String formatElapsed(Duration d) {
  final total = d.inSeconds;
  final h = total ~/ 3600;
  final m = (total % 3600) ~/ 60;
  final s = total % 60;
  String two(int v) => v.toString().padLeft(2, '0');
  return h > 0 ? '$h:${two(m)}:${two(s)}' : '${two(m)}:${two(s)}';
}
