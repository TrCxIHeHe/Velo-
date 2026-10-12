import 'dart:async';

import 'package:flutter/material.dart';
import 'package:scooter/core/utils/server_time.dart';

/// Live ride duration derived from the ride's real `started_at` instant.
///
/// It owns its own 1 s timer and rebuilds only itself, so the map and the rest
/// of the screen are not rebuilt every second, and a background refresh of the
/// ride never resets the clock (it is always `now - started_at`, not a counter).
class ElapsedDuration extends StatefulWidget {
  const ElapsedDuration({
    super.key,
    required this.startedAt,
    this.now = DateTime.now,
    this.style,
  });

  final DateTime startedAt;

  /// Injectable clock (tests).
  final DateTime Function() now;
  final TextStyle? style;

  @override
  State<ElapsedDuration> createState() => _ElapsedDurationState();
}

class _ElapsedDurationState extends State<ElapsedDuration> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = formatElapsed(elapsedSince(widget.startedAt, widget.now()));
    return Text(
      text,
      key: const Key('ride-duration'),
      style: widget.style ??
          const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, fontFeatures: [FontFeature.tabularFigures()]),
    );
  }
}
