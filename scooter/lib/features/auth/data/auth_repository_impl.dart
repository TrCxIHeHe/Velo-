import 'package:scooter/features/auth/data/auth_remote_datasource.dart';
import 'package:scooter/features/auth/domain/auth_repository.dart';
import 'package:scooter/features/auth/domain/models/session.dart';
import 'package:scooter/features/auth/domain/models/user.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl(this._ds);
  final AuthRemoteDataSource _ds;

  @override
  Future<Session> login(String firebaseIdToken) => _ds.login(firebaseIdToken);

  @override
  Future<void> logout(String refreshToken) => _ds.logout(refreshToken);

  @override
  Future<User> getMe() => _ds.getMe();

  @override
  Future<User> updateName(String name) => _ds.updateName(name);
}