import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';
import 'package:scooter/features/ride/presentation/providers/active_ride_providers.dart';
import 'package:scooter/features/ride/presentation/providers/ride_repository_providers.dart';
import 'package:scooter/features/ride/presentation/providers/ride_token_state.dart';

export 'package:scooter/features/ride/presentation/providers/ride_repository_providers.dart';

class RideTokenNotifier extends StateNotifier<RideTokenState> {
  RideTokenNotifier(this._repo, this._activeRide) : super(const RideTokenInitial());

  final RideRepository _repo;
  final ActiveRideNotifier _activeRide;

  /// Full flow: request ride (ignore RIDE_ALREADY_ACTIVE), then issue token.
  /// Call this on QR screen mount and on the "Get QR" button.
  Future<void> requestAndIssue() async {
    state = const RideTokenLoading();
    try {
      await _requestRideIgnoringActiveConflict();
      final token = await _repo.issueToken();
      state = RideTokenActive(token);
    } on ApiException catch (e) {
      state = RideTokenError(e.message, code: e.code);
    } catch (e) {
      state = RideTokenError(e.toString());
    }
  }

  /// Re-issue token only — for regenerate after expiry.
  /// The ride already exists; skip /ride/request.
  Future<void> regenerate() async {
    state = const RideTokenLoading();
    try {
      final token = await _repo.issueToken();
      state = RideTokenActive(token);
    } on ApiException catch (e) {
      // RIDE_INVALID_STATE here means the ride moved past ASSIGNED (e.g.
      // dock validated it). Treat as terminal error — ride is in progress.
      state = RideTokenError(e.message, code: e.code);
    } catch (e) {
      state = RideTokenError(e.toString());
    }
  }

  /// Called by the QR screen countdown when timer hits zero.
  void markExpired() {
    if (state is RideTokenActive) {
      state = const RideTokenExpired();
    }
  }

  void reset() => state = const RideTokenInitial();

  Future<void> _requestRideIgnoringActiveConflict() async {
    try {
      final ride = await _repo.requestRide();
      // Hand the fresh ride_id to the tracking notifier — this is the only
      // point the client ever learns it, since no GET /ride/active exists.
      await _activeRide.adopt(ride);
    } on ApiException catch (e) {
      // RIDE_ALREADY_ACTIVE means user already has an ASSIGNED ride.
      // That's fine for issuing a token — but we did NOT get a ride_id here.
      // If ActiveRideNotifier already has one persisted (e.g. this is the
      // same session that created it), tracking still works. If storage
      // was cleared, there is no backend endpoint to recover the id — see
      // missing-endpoint note in ride_repository.dart.
      if (e.code != 'RIDE_ALREADY_ACTIVE') rethrow;
    }
  }
}

final StateNotifierProvider<RideTokenNotifier, RideTokenState>
    rideTokenNotifierProvider =
    StateNotifierProvider<RideTokenNotifier, RideTokenState>(
  (ref) => RideTokenNotifier(
    ref.watch(rideRepositoryProvider),
    ref.watch(activeRideNotifierProvider.notifier),
  ),
);
