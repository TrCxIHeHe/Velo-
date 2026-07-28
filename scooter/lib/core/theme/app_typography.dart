import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Velo type scale (Figma "🎨 Design System" → "Typography"), built on
/// Inter. Sizes/weights/line-heights map 1:1 to the Figma labels.
abstract final class AppTypography {
  static TextTheme textTheme(Color primary, Color secondary) {
    final base = GoogleFonts.interTextTheme();
    return base.copyWith(
      displaySmall: GoogleFonts.inter(
        fontSize: 32,
        height: 38 / 32,
        fontWeight: FontWeight.w700,
        color: primary,
      ),
      headlineSmall: GoogleFonts.inter(
        fontSize: 24,
        height: 30 / 24,
        fontWeight: FontWeight.w700,
        color: primary,
      ),
      titleLarge: GoogleFonts.inter(
        fontSize: 20,
        height: 26 / 20,
        fontWeight: FontWeight.w600,
        color: primary,
      ),
      titleMedium: GoogleFonts.inter(
        fontSize: 17,
        height: 22 / 17,
        fontWeight: FontWeight.w600,
        color: primary,
      ),
      bodyLarge: GoogleFonts.inter(
        fontSize: 15,
        height: 22 / 15,
        fontWeight: FontWeight.w400,
        color: primary,
      ),
      bodyMedium: GoogleFonts.inter(
        fontSize: 15,
        height: 22 / 15,
        fontWeight: FontWeight.w500,
        color: primary,
      ),
      labelLarge: GoogleFonts.inter(
        fontSize: 13,
        height: 18 / 13,
        fontWeight: FontWeight.w500,
        color: secondary,
      ),
      bodySmall: GoogleFonts.inter(
        fontSize: 11,
        height: 16 / 11,
        fontWeight: FontWeight.w400,
        color: secondary,
      ),
    );
  }
}
