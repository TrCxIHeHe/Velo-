import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/theme/app_theme.dart';
import 'package:scooter/core/theme/theme_mode_controller.dart';
import 'package:scooter/router/app_router.dart';

class ScooterApp extends ConsumerWidget {
  const ScooterApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final themeMode = ref.watch(themeModeProvider);
    return MaterialApp.router(
      title: 'Velo',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: themeMode,
      routerConfig: router,
    );
  }
}
