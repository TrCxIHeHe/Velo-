import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';

class ThemeModeController extends StateNotifier<ThemeMode> {
  ThemeModeController(this._ref) : super(ThemeMode.system) {
    _restore();
  }

  final Ref _ref;

  Future<void> _restore() async {
    final storage = _ref.read(secureStorageProvider);
    final saved = await storage.getThemeMode();
    state = _fromString(saved) ?? ThemeMode.system;
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = mode;
    await _ref.read(secureStorageProvider).saveThemeMode(mode.name);
  }

  ThemeMode? _fromString(String? value) {
    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      case 'system':
        return ThemeMode.system;
      default:
        return null;
    }
  }
}

final StateNotifierProvider<ThemeModeController, ThemeMode>
    themeModeProvider = StateNotifierProvider<ThemeModeController, ThemeMode>(
  (ref) => ThemeModeController(ref),
);
