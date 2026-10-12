import 'dart:async';

import 'package:scooter/features/dock/domain/dock_repository.dart';
import 'package:scooter/features/dock/domain/models/dock.dart';
import 'package:scooter/features/ride/domain/models/fare_quote.dart';
import 'package:scooter/features/ride/domain/models/ride.dart';
import 'package:scooter/features/ride/domain/models/ride_token.dart';
import 'package:scooter/features/ride/domain/ride_repository.dart';
import 'package:scooter/features/wallet/domain/models/razorpay_order.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';
import 'package:scooter/features/wallet/domain/wallet_repository.dart';

Dock dock(
  String id, {
  String? name,
  int free = 3,
  bool active = true,
  double lat = 12.97,
  double lng = 77.59,
}) =>
    Dock(
      id: id,
      name: name ?? 'Dock $id',
      locationLat: lat,
      locationLng: lng,
      totalSlots: 5,
      availableSlots: free,
      isActive: active,
    );

Ride activeRide({String id = 'ride-1', String startDockId = 'A', DateTime? startedAt}) => Ride(
      id: id,
      userId: 'u',
      startDockId: startDockId,
      status: 'ACTIVE',
      fareCurrency: 'INR',
      createdAt: DateTime.utc(2026, 10, 11, 9),
      startedAt: startedAt ?? DateTime.utc(2026, 10, 11, 10),
    );

Ride completedRide({
  String id = 'ride-1',
  double fare = 20,
  String currency = 'INR',
  String? strategy = 'fixed_dock_pair',
  int duration = 754,
}) =>
    Ride(
      id: id,
      userId: 'u',
      startDockId: 'A',
      endDockId: 'B',
      status: 'COMPLETED',
      fareCurrency: currency,
      fareAmount: fare,
      pricingStrategy: strategy,
      durationSeconds: duration,
      createdAt: DateTime.utc(2026, 10, 11, 9),
      startedAt: DateTime.utc(2026, 10, 11, 10),
      endedAt: DateTime.utc(2026, 10, 11, 10, 12, 34),
    );

FareQuote quote(String destination, double amount, {bool? sufficient}) => FareQuote(
      rideId: 'ride-1',
      originDockId: 'A',
      destinationDockId: destination,
      fareAmount: amount,
      currency: 'INR',
      pricingStrategy: 'fixed_dock_pair',
      walletBalance: 100,
      sufficientBalance: sufficient,
    );

/// Dock repository whose list call can be completed manually.
class FakeDockRepository implements DockRepository {
  FakeDockRepository({this.docks = const []});

  List<Dock> docks;
  int listCalls = 0;

  /// When set, listDocks waits for this completer instead of answering.
  Completer<List<Dock>>? gate;
  Object? failWith;

  @override
  Future<List<Dock>> listDocks() async {
    listCalls++;
    if (gate != null) return gate!.future;
    if (failWith != null) throw failWith!;
    return docks;
  }

  @override
  Future<Dock> getDock(String dockId) async => docks.firstWhere((d) => d.id == dockId);
}

class FakeRideRepository implements RideRepository {
  FakeRideRepository({this.active});

  Ride? active;
  Completer<Ride?>? activeGate;
  Object? activeError;
  int activeCalls = 0;

  final Map<String, FutureOr<FareQuote> Function()> quotes = {};
  final List<String> quoteRequests = [];

  Future<Ride> Function(String rideId, String dockId)? onEnd;
  final List<(String, String)> endCalls = [];
  final List<String> cancelCalls = [];
  Ride? rideById;

  @override
  Future<Ride?> getActiveRide() async {
    activeCalls++;
    if (activeError != null) throw activeError!;
    if (activeGate != null) return activeGate!.future;
    return active;
  }

  @override
  Future<FareQuote> getFareQuote(String rideId, String destinationDockId) async {
    quoteRequests.add(destinationDockId);
    final make = quotes[destinationDockId];
    if (make == null) throw StateError('no quote stub for $destinationDockId');
    return make();
  }

  @override
  Future<Ride> endRide(String rideId, String dockId) {
    endCalls.add((rideId, dockId));
    return onEnd!(rideId, dockId);
  }

  @override
  Future<Ride> getRide(String id) async => rideById ?? completedRide(id: id);

  @override
  Future<Ride> cancelRide(String rideId) async {
    cancelCalls.add(rideId);
    return active!;
  }

  @override
  Future<RideToken> requestToken(String dockId) => throw UnimplementedError();
}

/// Wallet refresh after a ride is best effort; this keeps it off the network.
class FakeWalletRepository implements WalletRepository {
  @override
  Future<Wallet> getBalance() async => throw StateError('offline in tests');
  @override
  Future<TransactionPage> listTransactions({int skip = 0, int limit = 20}) async =>
      throw StateError('offline in tests');
  @override
  Future<Wallet> topUp(double amount, {String? referenceId}) async => throw StateError('offline in tests');
  @override
  Future<RazorpayOrder> createRazorpayOrder(double amount) async => throw StateError('offline in tests');
}
