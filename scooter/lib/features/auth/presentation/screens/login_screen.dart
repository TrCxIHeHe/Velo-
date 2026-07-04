import 'package:firebase_auth/firebase_auth.dart' as fb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';

enum _Step { phone, otp }

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  _Step _step = _Step.phone;
  final _phoneCtrl = TextEditingController();
  final _otpCtrl = TextEditingController();
  String? _verificationId;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }

  Future<void> _sendOtp() async {
    final phone = _phoneCtrl.text.trim();
    if (phone.isEmpty) {
      setState(() => _error = 'Enter your phone number.');
      return;
    }
    setState(() { _loading = true; _error = null; });

    await fb.FirebaseAuth.instance.verifyPhoneNumber(
      phoneNumber: phone,
      verificationCompleted: (cred) => _signIn(cred),
      verificationFailed: (e) => setState(() {
        _loading = false;
        _error = e.message ?? 'Verification failed.';
      }),
      codeSent: (id, _) => setState(() {
        _verificationId = id;
        _step = _Step.otp;
        _loading = false;
      }),
      codeAutoRetrievalTimeout: (_) {},
    );
  }

  Future<void> _verifyOtp() async {
    if (_otpCtrl.text.trim().length < 6) {
      setState(() => _error = 'Enter the 6-digit code.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    final cred = fb.PhoneAuthProvider.credential(
      verificationId: _verificationId!,
      smsCode: _otpCtrl.text.trim(),
    );
    await _signIn(cred);
  }

  Future<void> _signIn(fb.PhoneAuthCredential cred) async {
    try {
      final result =
          await fb.FirebaseAuth.instance.signInWithCredential(cred);
      final token = await result.user!.getIdToken();
      if (mounted) {
        await ref
            .read(authNotifierProvider.notifier)
            .loginWithFirebaseToken(token!);
      }
    } on fb.FirebaseAuthException catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.message; });
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AuthState>(authNotifierProvider, (_, s) {
      if (s is AuthError && mounted) {
        setState(() { _loading = false; _error = s.message; });
      }
    });

    return Scaffold(
      appBar: _step == _Step.otp
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => setState(() {
                  _step = _Step.phone;
                  _otpCtrl.clear();
                  _error = null;
                }),
              ),
              backgroundColor: Colors.transparent,
              elevation: 0,
            )
          : null,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _step == _Step.phone ? _buildPhone() : _buildOtp(),
        ),
      ),
    );
  }

  Widget _buildPhone() => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 48),
          Text('Welcome', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text('Enter your phone number to get started.',
              style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 40),
          TextField(
            controller: _phoneCtrl,
            keyboardType: TextInputType.phone,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Phone number',
              hintText: '+91 98765 43210',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.phone_outlined),
            ),
            onSubmitted: (_) => _sendOtp(),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!,
                style:
                    TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _loading ? null : _sendOtp,
              child: _loading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Send OTP'),
            ),
          ),
        ],
      );

  Widget _buildOtp() => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 48),
          Text('Verify OTP', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text('Code sent to ${_phoneCtrl.text.trim()}',
              style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 40),
          TextField(
            controller: _otpCtrl,
            keyboardType: TextInputType.number,
            maxLength: 6,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: '6-digit code',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.lock_outlined),
              counterText: '',
            ),
            onSubmitted: (_) => _verifyOtp(),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!,
                style:
                    TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _loading ? null : _verifyOtp,
              child: _loading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Verify'),
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: TextButton(
              onPressed: _loading ? null : _sendOtp,
              child: const Text('Resend OTP'),
            ),
          ),
        ],
      );
}