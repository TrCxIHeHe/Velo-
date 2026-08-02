import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';
import 'package:scooter/features/auth/presentation/screens/login_screen.dart';
import 'package:scooter/features/auth/presentation/screens/onboarding_screen.dart';
import 'package:scooter/features/auth/presentation/screens/profile_screen.dart';
import 'package:scooter/features/auth/presentation/screens/splash_screen.dart';
import 'package:scooter/features/ride/presentation/screens/qr_unlock_screen.dart';
import 'package:scooter/features/ride/presentation/screens/ride_receipt_screen.dart';
import 'package:scooter/features/ride/presentation/screens/ride_tracking_screen.dart';
import 'package:scooter/features/wallet/presentation/screens/recharge_screen.dart';
import 'package:scooter/features/wallet/presentation/screens/transaction_history_screen.dart';
import 'package:scooter/features/wallet/presentation/screens/wallet_screen.dart';
import 'package:scooter/router/home_shell.dart';

abstract final class AppRoutes {
  static const String splash = '/';
  static const String login = '/login';
  static const String onboarding = '/onboarding';
  static const String home = '/home';
  static const String profile = '/profile';
  static const String wallet = 'wallet';
  static const String recharge = 'wallet-recharge';
  static const String transactionHistory = 'wallet-transactions';
  static const String rideReceipt = 'ride-receipt';
  static const String qrUnlock = 'qr-unlock';
  static const String rideActive = 'ride-active';

  static const String walletPath = '/wallet';
  static const String rechargePath = '/wallet/recharge';
  static const String transactionHistoryPath = '/wallet/transactions';
  static const String rideActivePath = '/ride/active';
  static String rideReceiptPath(String rideId) => '/rides/$rideId/receipt';
}

final Provider<GoRouter> routerProvider = Provider<GoRouter>((ref) {
  final notifier = _RouterNotifier(ref);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: notifier,
    redirect: (context, state) {
      // Use the snapshot captured by _RouterNotifier so redirect is
      // always evaluated against the latest auth state.
      final auth = notifier.authState;
      final loc = state.matchedLocation;

      // App startup only.
      if (auth is AuthInitial) {
        return loc == AppRoutes.splash ? null : AppRoutes.splash;
      }

      // Interactive login/OTP verification.
      // Stay on the current screen while it completes.
      if (auth is AuthLoading) {
        return null;
      }

      // Not authenticated — go to login.
      if (auth is AuthUnauthenticated || auth is AuthError) {
        return loc == AppRoutes.login ? null : AppRoutes.login;
      }

      // Authenticated.
      if (auth is AuthAuthenticated) {
        final hasName = auth.user.name != null && auth.user.name!.isNotEmpty;

        // Redirect away from auth screens.
        if (loc == AppRoutes.splash || loc == AppRoutes.login) {
          return hasName ? AppRoutes.home : AppRoutes.onboarding;
        }

        // Force onboarding if name missing and not already there.
        if (!hasName && loc != AppRoutes.onboarding) {
          return AppRoutes.onboarding;
        }

        // Name set — don't let user linger on onboarding.
        if (hasName && loc == AppRoutes.onboarding) {
          return AppRoutes.home;
        }
      }

      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.onboarding,
        builder: (_, __) => const OnboardingScreen(),
      ),
      GoRoute(
        path: AppRoutes.home,
        builder: (_, __) => const HomeShell(),
      ),
      GoRoute(
        path: AppRoutes.profile,
        builder: (_, __) => const ProfileScreen(),
      ),
      GoRoute(
        path: AppRoutes.walletPath,
        name: AppRoutes.wallet,
        builder: (_, __) => const WalletScreen(),
        routes: [
          GoRoute(
            path: 'recharge',
            name: AppRoutes.recharge,
            builder: (_, __) => const RechargeScreen(),
          ),
          GoRoute(
            path: 'transactions',
            name: AppRoutes.transactionHistory,
            builder: (_, __) => const TransactionHistoryScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/rides/:id/receipt',
        name: AppRoutes.rideReceipt,
        builder: (_, state) => RideReceiptScreen(rideId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/docks/:dockId/unlock',
        name: AppRoutes.qrUnlock,
        builder: (_, state) => QrUnlockScreen(dockId: state.pathParameters['dockId']!),
      ),
      GoRoute(
        path: AppRoutes.rideActivePath,
        name: AppRoutes.rideActive,
        builder: (_, __) => const RideTrackingScreen(),
      ),
    ],
  );
});

class _RouterNotifier extends ChangeNotifier {
  _RouterNotifier(Ref ref) {
    // Watch auth state — every change triggers GoRouter to re-evaluate redirect.
    ref.listen<AuthState>(authNotifierProvider, (_, next) {
      authState = next;
      notifyListeners();
    });
    // Capture initial state so redirect has a value before first change.
    authState = ref.read(authNotifierProvider);
  }

  late AuthState authState;
}
