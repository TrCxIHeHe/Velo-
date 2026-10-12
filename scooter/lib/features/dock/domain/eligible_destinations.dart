import 'package:scooter/features/dock/domain/models/dock.dart';

/// Docks a ride may be ended at: active, with a free return slot, and not the
/// dock the ride started from (returning to the origin is not allowed).
///
/// Client-side filtering is only a convenience; the backend re-validates
/// availability and the tariff when the ride is actually ended.
List<Dock> eligibleDestinations(List<Dock> docks, {required String originDockId}) {
  final result = docks
      .where((d) => d.isActive && d.availableSlots > 0 && d.id != originDockId)
      .toList()
    ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  return result;
}
