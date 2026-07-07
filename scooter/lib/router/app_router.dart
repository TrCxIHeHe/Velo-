import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';
import 'package:scooter/features/auth/presentation/screens/login_screen.dart';
import 'package:scooter/features/auth/presentation/screens/onboarding_screen.dart';
import 'package:scooter/features/auth/presentation/screens/profile_screen.dart';
import 'package:scooter/features/auth/presentation/screens/splash_screen.dart';

abstract final class AppRoutes {
  static const String splash = '/';
  static const String login = '/login';
  static const String onboarding = '/onboarding';
  static const String profile = '/profile';
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

      // While session check is in progress, stay on splash.
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

        // Redirect away from auth screens.
        if (loc == AppRoutes.splash || loc == AppRoutes.login) {
          return hasName ? AppRoutes.profile : AppRoutes.onboarding;
        }

        // Force onboarding if name missing and not already there.
        if (!hasName && loc != AppRoutes.onboarding) {
          return AppRoutes.onboarding;
        }

        // Name set — don't let user linger on onboarding.
        if (hasName && loc == AppRoutes.onboarding) {
          return AppRoutes.profile;
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
        path: AppRoutes.profile,
        builder: (_, __) => const ProfileScreen(),
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
