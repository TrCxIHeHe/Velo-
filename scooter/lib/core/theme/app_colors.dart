import 'package:flutter/material.dart';

/// Velo design-system color tokens, pulled from the Figma file
/// "Velo — MVP Design System · Prototype" (page "🎨 Design System" →
/// "Color Palette"). Dark-mode values are authored to match the same
/// semantic roles at proper contrast — Figma only defines light mode.
abstract final class AppColors {
  static const Color brandPrimary = Color(0xFF0F9D58);
  static const Color brandPrimaryDark = Color(0xFF0B7A44);
  static const Color brandOnPrimary = Color(0xFFFFFFFF);

  static const Color surfaceBg = Color(0xFFF7F9F8);
  static const Color surfaceCard = Color(0xFFFFFFFF);
  static const Color surfaceElevated = Color(0xFFFFFFFF);
  static const Color surfaceOutline = Color(0xFFE2E8E4);

  static const Color textPrimary = Color(0xFF12241B);
  static const Color textSecondary = Color(0xFF5C6B63);
  static const Color textMuted = Color(0xFF8FA097);

  static const Color stateSuccess = Color(0xFF0F9D58);
  static const Color stateError = Color(0xFFD64550);
  static const Color stateErrorBg = Color(0xFFFBE9EA);
  static const Color stateWarning = Color(0xFFE8A93B);
  static const Color accentAmber = Color(0xFFE8A93B);

  static const Color chipSuccessBg = Color(0xFFE5F5EB);
  static const Color chipOfflineBg = Color(0xFFEBEDEB);
  static const Color chipErrorBg = Color(0xFFFAE8EB);

  static const Color snackbarBg = Color(0xFF12241A);
}

/// Dark-mode counterparts, keeping the brand green but tuned for
/// contrast on near-black surfaces, and following the same naming.
abstract final class AppColorsDark {
  static const Color brandPrimary = Color(0xFF22C176);
  static const Color brandPrimaryDark = Color(0xFF1A9C5E);
  static const Color brandOnPrimary = Color(0xFF06120C);

  static const Color surfaceBg = Color(0xFF0E1512);
  static const Color surfaceCard = Color(0xFF17211C);
  static const Color surfaceElevated = Color(0xFF1E2A24);
  static const Color surfaceOutline = Color(0xFF2A3830);

  static const Color textPrimary = Color(0xFFF2F5F3);
  static const Color textSecondary = Color(0xFFB7C4BD);
  static const Color textMuted = Color(0xFF7C8F85);

  static const Color stateSuccess = Color(0xFF22C176);
  static const Color stateError = Color(0xFFEF5F68);
  static const Color stateErrorBg = Color(0xFF3A1E21);
  static const Color stateWarning = Color(0xFFF0B955);
  static const Color accentAmber = Color(0xFFF0B955);

  static const Color chipSuccessBg = Color(0xFF163826);
  static const Color chipOfflineBg = Color(0xFF232C28);
  static const Color chipErrorBg = Color(0xFF3A1E21);

  static const Color snackbarBg = Color(0xFF0A0F0C);
}
