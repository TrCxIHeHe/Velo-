import 'package:flutter/material.dart';
import 'package:scooter/core/theme/app_colors.dart';
import 'package:scooter/core/theme/app_semantic_colors.dart';
import 'package:scooter/core/theme/app_typography.dart';

abstract final class AppTheme {
  static ThemeData get light {
    const colorScheme = ColorScheme.light(
      primary: AppColors.brandPrimary,
      onPrimary: AppColors.brandOnPrimary,
      secondary: AppColors.brandPrimaryDark,
      onSecondary: AppColors.brandOnPrimary,
      surface: AppColors.surfaceCard,
      onSurface: AppColors.textPrimary,
      error: AppColors.stateError,
      onError: AppColors.brandOnPrimary,
      outline: AppColors.surfaceOutline,
    );
    return _build(
      colorScheme: colorScheme,
      scaffoldBg: AppColors.surfaceBg,
      textTheme: AppTypography.textTheme(
        AppColors.textPrimary,
        AppColors.textSecondary,
      ),
      semanticColors: AppSemanticColors.light,
    );
  }

  static ThemeData get dark {
    const colorScheme = ColorScheme.dark(
      primary: AppColorsDark.brandPrimary,
      onPrimary: AppColorsDark.brandOnPrimary,
      secondary: AppColorsDark.brandPrimaryDark,
      onSecondary: AppColorsDark.brandOnPrimary,
      surface: AppColorsDark.surfaceCard,
      onSurface: AppColorsDark.textPrimary,
      error: AppColorsDark.stateError,
      onError: AppColorsDark.textPrimary,
      outline: AppColorsDark.surfaceOutline,
    );
    return _build(
      colorScheme: colorScheme,
      scaffoldBg: AppColorsDark.surfaceBg,
      textTheme: AppTypography.textTheme(
        AppColorsDark.textPrimary,
        AppColorsDark.textSecondary,
      ),
      semanticColors: AppSemanticColors.dark,
    );
  }

  static ThemeData _build({
    required ColorScheme colorScheme,
    required Color scaffoldBg,
    required TextTheme textTheme,
    required AppSemanticColors semanticColors,
  }) {
    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: scaffoldBg,
      textTheme: textTheme,
      extensions: [semanticColors],
      appBarTheme: AppBarTheme(
        backgroundColor: scaffoldBg,
        foregroundColor: colorScheme.onSurface,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: textTheme.headlineSmall?.copyWith(fontSize: 20),
      ),
      cardTheme: CardThemeData(
        color: colorScheme.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: colorScheme.outline),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: colorScheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: semanticColors.snackbarBg,
        contentTextStyle: textTheme.labelLarge?.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w500,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      dividerTheme: DividerThemeData(color: colorScheme.outline),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: colorScheme.surface,
        selectedItemColor: colorScheme.primary,
        unselectedItemColor: semanticColors.textMuted,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.error, width: 1.5),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.error, width: 1.5),
        ),
        hintStyle: textTheme.bodyLarge?.copyWith(color: semanticColors.textMuted),
        labelStyle: textTheme.labelLarge,
      ),
    );
  }
}
