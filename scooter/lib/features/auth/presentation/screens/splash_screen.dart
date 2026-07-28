import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/security/device_integrity.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  bool _checkingDevice = true;
  bool _compromised = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final compromised = await isDeviceCompromised();
    if (!mounted) return;
    setState(() {
      _compromised = compromised;
      _checkingDevice = false;
    });
    if (!compromised) {
      ref.read(authNotifierProvider.notifier).checkSession();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checkingDevice) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_compromised) {
      return _CompromisedDeviceView();
    }

    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(color: scheme.primary, shape: BoxShape.circle),
              child: Icon(Icons.pedal_bike_outlined, color: scheme.onPrimary, size: 36),
            ),
            const SizedBox(height: 20),
            Text('Velo', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(
              'Ride the city, dock to dock.',
              style: TextStyle(color: Theme.of(context).hintColor, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}

class _CompromisedDeviceView extends StatelessWidget {
  const _CompromisedDeviceView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.gpp_bad_outlined,
                    size: 56, color: Theme.of(context).colorScheme.error),
                const SizedBox(height: 16),
                Text('Unsupported device', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(
                  "Velo can't run on a rooted or jailbroken device — this protects "
                  'your wallet and ride tokens from tampering.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 24),
                SecondaryButton(
                  label: 'Exit',
                  onPressed: () => SystemNavigator.pop(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
