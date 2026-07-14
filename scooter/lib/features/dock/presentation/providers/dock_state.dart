import 'package:scooter/features/dock/domain/models/dock.dart';

sealed class DockState {
  const DockState();
}

final class DockInitial extends DockState {
  const DockInitial();
}

final class DockLoading extends DockState {
  const DockLoading();
}

final class DockLoaded extends DockState {
  const DockLoaded(this.docks);
  final List<Dock> docks;
}

final class DockError extends DockState {
  const DockError(this.message);
  final String message;
}
