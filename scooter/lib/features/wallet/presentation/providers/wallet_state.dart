import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

sealed class WalletState {
  const WalletState();
}

final class WalletInitial extends WalletState {
  const WalletInitial();
}

final class WalletLoading extends WalletState {
  const WalletLoading();
}

final class WalletLoaded extends WalletState {
  const WalletLoaded({required this.wallet, required this.transactions});
  final Wallet wallet;
  final List<WalletTransaction> transactions;
}

final class WalletError extends WalletState {
  const WalletError(this.message);
  final String message;
}
