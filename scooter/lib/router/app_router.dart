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
    final auth = ref.read(authNotifierProvider);
    final loc = state.matchedLocation;

    if (auth is AuthInitial || auth is AuthLoading) {
      return loc == AppRoutes.splash ? null : AppRoutes.splash;
    }

    if (auth is AuthUnauthenticated || auth is AuthError) {
      return loc == AppRoutes.login ? null : AppRoutes.login;
    }

    if (auth is AuthAuthenticated) {
      final hasName = auth.user.name != null;

      if (loc == AppRoutes.login || loc == AppRoutes.splash) {
        return hasName
            ? AppRoutes.profile
            : AppRoutes.onboarding;
      }

      if (!hasName && loc != AppRoutes.onboarding) {
        return AppRoutes.onboarding;
      }
    }

    return null;
},
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (_, __) => const SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (_, __) => const LoginScreen()),
      GoRoute(path: AppRoutes.onboarding, builder: (_, __) => const OnboardingScreen()),
      GoRoute(path: AppRoutes.profile, builder: (_, __) => const ProfileScreen()),
    ],
  );
});

class _RouterNotifier extends ChangeNotifier {
  _RouterNotifier(Ref ref) {
    ref.listen(authNotifierProvider, (_, __) => notifyListeners());
  }
}