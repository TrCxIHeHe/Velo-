import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';
import 'package:scooter/features/auth/presentation/screens/login_screen.dart';
import 'package:scooter/features/auth/presentation/screens/onboarding_screen.dart';
import 'package:scooter/features/auth/presentation/screens/splash_screen.dart';
import 'package:scooter/features/home/presentation/screens/home_screen.dart';

abstract final class AppRoutes {
  static const String splash = '/';
  static const String login = '/login';
  static const String onboarding = '/onboarding';
  // /profile is retired as a top-level route — it lives inside HomeScreen tab.
  // Keep the constant so any stale string references resolve without error.
  static const String profile = '/home';
  static const String home = '/home';
}

final Provider<GoRouter> routerProvider = Provider<GoRouter>((ref) {
  final notifier = _RouterNotifier(ref);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: notifier,
    redirect: (context, state) {
      final auth = notifier.authState;
      final loc = state.matchedLocation;

      // Session check in progress — hold on splash.
      if (auth is AuthInitial || auth is AuthLoading) {
        return loc == AppRoutes.splash ? null : AppRoutes.splash;
      }

      // Not authenticated — go to login.
      if (auth is AuthUnauthenticated || auth is AuthError) {
        return loc == AppRoutes.login ? null : AppRoutes.login;
      }

      // Authenticated.
      if (auth is AuthAuthenticated) {
        final hasName = auth.user.name != null && auth.user.name!.isNotEmpty;

        // Redirect away from auth-only screens.
        if (loc == AppRoutes.splash || loc == AppRoutes.login) {
          return hasName ? AppRoutes.home : AppRoutes.onboarding;
        }

        // Force onboarding if name missing.
        if (!hasName && loc != AppRoutes.onboarding) {
          return AppRoutes.onboarding;
        }

        // Name set — don't stay on onboarding.
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
        builder: (_, __) => const HomeScreen(),
      ),
    ],
  );
});

class _RouterNotifier extends ChangeNotifier {
  _RouterNotifier(Ref ref) {
    ref.listen<AuthState>(authNotifierProvider, (_, next) {
      authState = next;
      notifyListeners();
    });
    authState = ref.read(authNotifierProvider);
  }

  late AuthState authState;
}