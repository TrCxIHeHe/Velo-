import 'package:flutter/material.dart';
import 'package:scooter/features/auth/presentation/screens/profile_screen.dart';
import 'package:scooter/features/dock/presentation/screens/map_screen.dart';
import 'package:scooter/features/dock/presentation/screens/unlock_screen.dart';
import 'package:scooter/features/ride/presentation/screens/ride_tracking_screen.dart';
import 'package:scooter/features/wallet/presentation/screens/wallet_screen.dart';

/// Persistent bottom-nav shell (Map · Unlock · Ride · Wallet · Profile),
/// matching the Figma bottom-nav component present on every post-login
/// screen. Each tab keeps its own state via IndexedStack.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _tabs = [
    MapScreen(),
    UnlockScreen(),
    RideTrackingScreen(),
    WalletScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _tabs),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Map'),
          NavigationDestination(
              icon: Icon(Icons.qr_code_2_outlined), selectedIcon: Icon(Icons.qr_code_2), label: 'Unlock'),
          NavigationDestination(
              icon: Icon(Icons.pedal_bike_outlined), selectedIcon: Icon(Icons.pedal_bike), label: 'Ride'),
          NavigationDestination(
              icon: Icon(Icons.account_balance_wallet_outlined),
              selectedIcon: Icon(Icons.account_balance_wallet),
              label: 'Wallet'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
