import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:scooter/app.dart';
import 'package:scooter/firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  print("STARTING FIREBASE");

  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  
  print("FIREBASE DONE");
  runApp(const ProviderScope(child: ScooterApp()));
}