import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/features/auth/presentation/screens/profile_screen.dart';
import 'package:scooter/features/dock/presentation/screens/map_screen.dart';
import 'package:scooter/features/ride/presentation/providers/active_ride_providers.dart';
import 'package:scooter/features/ride/presentation/screens/qr_screen.dart';
import 'package:scooter/features/ride/presentation/screens/ride_tracking_screen.dart';
import 'package:scooter/features/wallet/presentation/screens/wallet_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _selectedIndex = 0;

  // IndexedStack keeps all tabs alive — avoids re-fetching on tab switch.
  static const _tabs = [
    MapScreen(),
    QrScreen(),
    RideTrackingScreen(),
    WalletScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    // Resume any in-progress ride regardless of which tab the user lands
    // on first — this is what lets the Ride tab show a live card after
    // an app restart mid-ride.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(activeRideNotifierProvider.notifier).resume();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: _tabs,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map_rounded),
            label: 'Map',
          ),
          NavigationDestination(
            icon: Icon(Icons.qr_code_outlined),
            selectedIcon: Icon(Icons.qr_code_2_rounded),
            label: 'Unlock',
          ),
          NavigationDestination(
            icon: Icon(Icons.electric_scooter_outlined),
            selectedIcon: Icon(Icons.electric_scooter_rounded),
            label: 'Ride',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet_rounded),
            label: 'Wallet',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outlined),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}
