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
  const WalletLoaded(this.wallet, this.recentTransactions);
  final Wallet wallet;
  final List<WalletTransaction> recentTransactions;
}

final class WalletError extends WalletState {
  const WalletError(this.message);
  final String message;
}
