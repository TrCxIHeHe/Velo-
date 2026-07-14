import 'package:scooter/features/ride/domain/models/ride_token.dart';

sealed class RideTokenState {
  const RideTokenState();
}

/// No ride token requested yet — initial tab state.
final class RideTokenInitial extends RideTokenState {
  const RideTokenInitial();
}

/// POST /ride/request or POST /ride/token in flight.
final class RideTokenLoading extends RideTokenState {
  const RideTokenLoading();
}

/// Token issued and not yet expired.
final class RideTokenActive extends RideTokenState {
  const RideTokenActive(this.token);
  final RideToken token;
}

/// Token TTL elapsed — user must regenerate.
final class RideTokenExpired extends RideTokenState {
  const RideTokenExpired();
}

/// Backend or network error during request or token issue.
final class RideTokenError extends RideTokenState {
  const RideTokenError(this.message, {this.code});
  final String message;
  // Backend error code — e.g. RIDE_ALREADY_ACTIVE, RIDE_INVALID_STATE
  final String? code;
}
