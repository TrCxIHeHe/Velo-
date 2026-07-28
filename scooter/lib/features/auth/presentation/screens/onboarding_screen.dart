import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/app_text_field.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _nameCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Enter your name.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    await ref.read(authNotifierProvider.notifier).updateName(name);
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AuthState>(authNotifierProvider, (_, s) {
      if (s is AuthError && mounted) {
        setState(() {
          _loading = false;
          _error = s.message;
        });
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 48),
              Text("What's your name?", style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(
                "This is how you'll appear in the app.",
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 40),
              AppTextField(
                label: 'Full name',
                controller: _nameCtrl,
                hintText: 'Full name',
                prefixIcon: Icons.person_outlined,
                autofocus: true,
                errorText: _error,
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 24),
              PrimaryButton(label: 'Continue', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
      ),
    );
  }
}
