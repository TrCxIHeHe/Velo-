import 'package:scooter/features/auth/domain/models/session.dart';
import 'package:scooter/features/auth/domain/models/user.dart';

abstract interface class AuthRepository {
  Future<Session> login(String firebaseIdToken);
  Future<void> logout(String refreshToken);
  Future<User> getMe();
  Future<User> updateName(String name);
}