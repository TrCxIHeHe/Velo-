import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/ride/data/ride_remote_datasource.dart';
import 'package:scooter/features/ride/data/ride_repository_impl.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';
import 'package:scooter/features/ride/presentation/providers/ride_token_state.dart';

final Provider<RideRemoteDataSource> rideDataSourceProvider =
    Provider<RideRemoteDataSource>(
  (ref) => RideRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<RideRepository> rideRepositoryProvider =
    Provider<RideRepository>(
  (ref) => RideRepositoryImpl(ref.watch(rideDataSourceProvider)),
);

class RideTokenNotifier extends StateNotifier<RideTokenState> {
  RideTokenNotifier(this._repo) : super(const RideTokenInitial());

  final RideRepository _repo;

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
      await _repo.requestRide();
    } on ApiException catch (e) {
      // RIDE_ALREADY_ACTIVE means user already has an ASSIGNED ride.
      // That's fine — we'll issue a token for it.
      if (e.code != 'RIDE_ALREADY_ACTIVE') rethrow;
    }
  }
}

final StateNotifierProvider<RideTokenNotifier, RideTokenState>
    rideTokenNotifierProvider =
    StateNotifierProvider<RideTokenNotifier, RideTokenState>(
  (ref) => RideTokenNotifier(ref.watch(rideRepositoryProvider)),
);
