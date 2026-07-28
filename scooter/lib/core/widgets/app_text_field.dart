import 'package:flutter/material.dart';

/// Label above a bordered input field, matching the Figma "Input Field"
/// component — label 13/medium, field radius 12, error caption below.
class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    required this.label,
    this.controller,
    this.hintText,
    this.errorText,
    this.keyboardType,
    this.prefixIcon,
    this.maxLength,
    this.autofocus = false,
    this.onSubmitted,
    this.onChanged,
    this.textAlign = TextAlign.start,
  });

  final String label;
  final TextEditingController? controller;
  final String? hintText;
  final String? errorText;
  final TextInputType? keyboardType;
  final IconData? prefixIcon;
  final int? maxLength;
  final bool autofocus;
  final ValueChanged<String>? onSubmitted;
  final ValueChanged<String>? onChanged;
  final TextAlign textAlign;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.labelLarge),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          maxLength: maxLength,
          autofocus: autofocus,
          textAlign: textAlign,
          onSubmitted: onSubmitted,
          onChanged: onChanged,
          style: theme.textTheme.bodyLarge,
          decoration: InputDecoration(
            hintText: hintText,
            errorText: errorText,
            counterText: '',
            prefixIcon: prefixIcon != null ? Icon(prefixIcon, size: 20) : null,
          ),
        ),
      ],
    );
  }
}
