import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/core/theme/theme_mode_controller.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/features/auth/domain/models/user.dart';
import 'package:scooter/features/auth/presentation/providers/auth_providers.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(authNotifierProvider);
    if (state is! AuthAuthenticated) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final User user = state.user;
    final themeMode = ref.watch(themeModeProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(authNotifierProvider.notifier).refreshProfile(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const SizedBox(height: 16),
          Center(
            child: CircleAvatar(
              radius: 40,
              child: Text(
                (user.name ?? user.phoneNumber)[0].toUpperCase(),
                style: const TextStyle(fontSize: 32),
              ),
            ),
          ),
          const SizedBox(height: 32),
          _Tile(icon: Icons.person_outlined, label: 'Name', value: user.name ?? '—'),
          const Divider(),
          _Tile(icon: Icons.phone_outlined, label: 'Phone', value: user.phoneNumber),
          const Divider(),
          _Tile(icon: Icons.badge_outlined, label: 'Role', value: user.role),
          const Divider(),
          const SizedBox(height: 8),
          Text('Appearance', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          SegmentedButton<ThemeMode>(
            segments: const [
              ButtonSegment(value: ThemeMode.system, label: Text('System'), icon: Icon(Icons.brightness_auto)),
              ButtonSegment(value: ThemeMode.light, label: Text('Light'), icon: Icon(Icons.light_mode_outlined)),
              ButtonSegment(value: ThemeMode.dark, label: Text('Dark'), icon: Icon(Icons.dark_mode_outlined)),
            ],
            selected: {themeMode},
            onSelectionChanged: (selection) =>
                ref.read(themeModeProvider.notifier).setThemeMode(selection.first),
          ),
          const SizedBox(height: 40),
          DangerOutlineButton(
            label: 'Log out',
            icon: Icons.logout,
            onPressed: () => _confirmLogout(context, ref),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Log out'),
        content: const Text('Are you sure you want to log out?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Log out')),
        ],
      ),
    );
    if (ok == true && context.mounted) {
      await ref.read(authNotifierProvider.notifier).logout();
    }
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 2),
              Text(value, style: Theme.of(context).textTheme.bodyLarge),
            ],
          ),
        ],
      ),
    );
  }
}
