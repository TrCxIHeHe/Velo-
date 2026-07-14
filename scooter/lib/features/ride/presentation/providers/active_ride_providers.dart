import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/storage/secure_storage.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';
import 'package:scooter/features/ride/presentation/providers/active_ride_state.dart';
import 'package:scooter/features/ride/presentation/providers/ride_repository_providers.dart';

const _pollInterval = Duration(seconds: 4);

class ActiveRideNotifier extends StateNotifier<ActiveRideState> {
  ActiveRideNotifier(this._repo, this._storage) : super(const ActiveRideNone());

  final RideRepository _repo;
  final SecureStorageService _storage;
  Timer? _pollTimer;

  /// Call on app start / tab mount. Reads a persisted ride_id (the only
  /// recovery path — no GET /ride/active endpoint exists) and re-syncs.
  Future<void> resume() async {
    final storedId = await _storage.getActiveRideId();
    if (storedId == null) {
      state = const ActiveRideNone();
      return;
    }
    state = const ActiveRideLoading();
    await _refreshRide(storedId);
    if (state is ActiveRideTracking) _startPolling(storedId);
  }

  /// Called by the QR flow immediately after POST /ride/request succeeds.
  /// This is the only moment the client ever receives a fresh ride_id.
  Future<void> adopt(Ride ride) async {
    await _storage.saveActiveRideId(ride.id);
    if (ride.isTerminal) {
      state = ActiveRideEnded(ride);
      await _storage.clearActiveRideId();
    } else {
      state = ActiveRideTracking(ride);
      _startPolling(ride.id);
    }
  }

  /// User acknowledges a completed/cancelled ride — clears local state.
  Future<void> dismiss() async {
    _pollTimer?.cancel();
    await _storage.clearActiveRideId();
    state = const ActiveRideNone();
  }

  Future<void> refreshNow() async {
    final id = _currentRideId();
    if (id != null) await _refreshRide(id);
  }

  String? _currentRideId() => switch (state) {
        ActiveRideTracking(:final ride) => ride.id,
        ActiveRideEnded(:final ride) => ride.id,
        _ => null,
      };

  void _startPolling(String rideId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(_pollInterval, (_) => _refreshRide(rideId));
  }

  Future<void> _refreshRide(String rideId) async {
    try {
      final ride = await _repo.getRide(rideId);
      if (ride.isTerminal) {
        _pollTimer?.cancel();
        state = ActiveRideEnded(ride);
        await _storage.clearActiveRideId();
      } else {
        state = ActiveRideTracking(ride);
      }
    } catch (e) {
      // Transient network failure during a poll tick — keep showing the
      // last known state rather than flashing an error every 4 seconds.
      if (state is! ActiveRideTracking) {
        state = ActiveRideError(e.toString());
      }
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}

final StateNotifierProvider<ActiveRideNotifier, ActiveRideState>
    activeRideNotifierProvider =
    StateNotifierProvider<ActiveRideNotifier, ActiveRideState>(
  (ref) => ActiveRideNotifier(
    ref.watch(rideRepositoryProvider),
    ref.watch(secureStorageProvider),
  ),
);
