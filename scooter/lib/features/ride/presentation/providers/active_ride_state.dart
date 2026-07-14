import 'package:scooter/features/ride/domain/models/ride.dart';

sealed class ActiveRideState {
  const ActiveRideState();
}

/// No ride requested/resumed yet.
final class ActiveRideNone extends ActiveRideState {
  const ActiveRideNone();
}

final class ActiveRideLoading extends ActiveRideState {
  const ActiveRideLoading();
}

/// A ride exists and is in a non-terminal state (ASSIGNED..END_PENDING).
final class ActiveRideTracking extends ActiveRideState {
  const ActiveRideTracking(this.ride);
  final Ride ride;
}

/// Ride reached a terminal state (COMPLETED/CANCELLED/FAILED/FORCE_TERMINATED).
final class ActiveRideEnded extends ActiveRideState {
  const ActiveRideEnded(this.ride);
  final Ride ride;
}

final class ActiveRideError extends ActiveRideState {
  const ActiveRideError(this.message);
  final String message;
}
