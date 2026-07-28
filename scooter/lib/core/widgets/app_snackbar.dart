import 'package:flutter/material.dart';

/// Dark pill snackbar (Figma `3:37`) — styling comes from
/// `SnackBarThemeData` in `app_theme.dart`; this just standardizes usage.
void showAppSnackbar(BuildContext context, String message, {bool isError = false}) {
  final scheme = Theme.of(context).colorScheme;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? scheme.error : null,
      ),
    );
}
