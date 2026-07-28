import 'package:flutter/material.dart';
import 'package:scooter/core/theme/app_colors.dart';

/// Design tokens that don't have a slot in Material's [ColorScheme] —
/// muted text, chip fills, snackbar background. Access via
/// `Theme.of(context).extension<AppSemanticColors>()!`.
@immutable
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  const AppSemanticColors({
    required this.textMuted,
    required this.stateSuccess,
    required this.stateWarning,
    required this.stateErrorBg,
    required this.chipSuccessBg,
    required this.chipOfflineBg,
    required this.chipErrorBg,
    required this.snackbarBg,
    required this.surfaceElevated,
  });

  final Color textMuted;
  final Color stateSuccess;
  final Color stateWarning;
  final Color stateErrorBg;
  final Color chipSuccessBg;
  final Color chipOfflineBg;
  final Color chipErrorBg;
  final Color snackbarBg;
  final Color surfaceElevated;

  static const light = AppSemanticColors(
    textMuted: AppColors.textMuted,
    stateSuccess: AppColors.stateSuccess,
    stateWarning: AppColors.stateWarning,
    stateErrorBg: AppColors.stateErrorBg,
    chipSuccessBg: AppColors.chipSuccessBg,
    chipOfflineBg: AppColors.chipOfflineBg,
    chipErrorBg: AppColors.chipErrorBg,
    snackbarBg: AppColors.snackbarBg,
    surfaceElevated: AppColors.surfaceElevated,
  );

  static const dark = AppSemanticColors(
    textMuted: AppColorsDark.textMuted,
    stateSuccess: AppColorsDark.stateSuccess,
    stateWarning: AppColorsDark.stateWarning,
    stateErrorBg: AppColorsDark.stateErrorBg,
    chipSuccessBg: AppColorsDark.chipSuccessBg,
    chipOfflineBg: AppColorsDark.chipOfflineBg,
    chipErrorBg: AppColorsDark.chipErrorBg,
    snackbarBg: AppColorsDark.snackbarBg,
    surfaceElevated: AppColorsDark.surfaceElevated,
  );

  @override
  AppSemanticColors copyWith({
    Color? textMuted,
    Color? stateSuccess,
    Color? stateWarning,
    Color? stateErrorBg,
    Color? chipSuccessBg,
    Color? chipOfflineBg,
    Color? chipErrorBg,
    Color? snackbarBg,
    Color? surfaceElevated,
  }) {
    return AppSemanticColors(
      textMuted: textMuted ?? this.textMuted,
      stateSuccess: stateSuccess ?? this.stateSuccess,
      stateWarning: stateWarning ?? this.stateWarning,
      stateErrorBg: stateErrorBg ?? this.stateErrorBg,
      chipSuccessBg: chipSuccessBg ?? this.chipSuccessBg,
      chipOfflineBg: chipOfflineBg ?? this.chipOfflineBg,
      chipErrorBg: chipErrorBg ?? this.chipErrorBg,
      snackbarBg: snackbarBg ?? this.snackbarBg,
      surfaceElevated: surfaceElevated ?? this.surfaceElevated,
    );
  }

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      stateSuccess: Color.lerp(stateSuccess, other.stateSuccess, t)!,
      stateWarning: Color.lerp(stateWarning, other.stateWarning, t)!,
      stateErrorBg: Color.lerp(stateErrorBg, other.stateErrorBg, t)!,
      chipSuccessBg: Color.lerp(chipSuccessBg, other.chipSuccessBg, t)!,
      chipOfflineBg: Color.lerp(chipOfflineBg, other.chipOfflineBg, t)!,
      chipErrorBg: Color.lerp(chipErrorBg, other.chipErrorBg, t)!,
      snackbarBg: Color.lerp(snackbarBg, other.snackbarBg, t)!,
      surfaceElevated: Color.lerp(surfaceElevated, other.surfaceElevated, t)!,
    );
  }
}

extension AppSemanticColorsX on BuildContext {
  AppSemanticColors get semanticColors =>
      Theme.of(this).extension<AppSemanticColors>()!;
}
