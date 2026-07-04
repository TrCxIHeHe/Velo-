import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:scooter/core/network/dio_client.dart';
import 'package:scooter/core/storage/secure_storage.dart';
import 'package:scooter/features/auth/data/auth_remote_datasource.dart';
import 'package:scooter/features/auth/data/auth_repository_impl.dart';
import 'package:scooter/features/auth/domain/auth_repository.dart';
import 'package:scooter/features/auth/domain/models/user.dart';
import 'package:scooter/features/auth/presentation/providers/auth_state.dart';

final Provider<SecureStorageService> secureStorageProvider =
    Provider<SecureStorageService>(
  (ref) => const SecureStorageService(FlutterSecureStorage()),
);

final Provider<Dio> dioProvider = Provider<Dio>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return createDio(
    storage,
    () => ref.read(authNotifierProvider.notifier).onSessionExpired(),
  );
});

final Provider<AuthRemoteDataSource> authDataSourceProvider =
    Provider<AuthRemoteDataSource>(
  (ref) => AuthRemoteDataSource(ref.watch(dioProvider)),
);

final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>(
  (ref) => AuthRepositoryImpl(ref.watch(authDataSourceProvider)),
);

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._repo, this._storage) : super(const AuthInitial());

  final AuthRepository _repo;
  final SecureStorageService _storage;

Future<void> checkSession() async {
  print("CHECK SESSION START");

  final token = await _storage.getAccessToken();

  print("TOKEN = $token");

  if (token == null) {
    print("NO TOKEN");
    state = const AuthUnauthenticated();
    return;
  }

  try {
    print("CALLING GETME");

    final user = await _repo.getMe();

    print("AUTHENTICATED");

    state = AuthAuthenticated(user);
  } catch (e) {
    print("GETME ERROR: $e");

    await _storage.clearSession();

    state = const AuthUnauthenticated();
  }
}

  Future<void> loginWithFirebaseToken(String firebaseIdToken) async {
    state = const AuthLoading();
    try {
      final session = await _repo.login(firebaseIdToken);
      await _storage.saveSession(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );
      state = AuthAuthenticated(session.user);
    } catch (e) {
      state = AuthError(e.toString());
    }
  }

  Future<void> updateName(String name) async {
    try {
      final user = await _repo.updateName(name);
      state = AuthAuthenticated(user);
    } catch (e) {
      state = AuthError(e.toString());
    }
  }

  Future<void> refreshProfile() async {
    try {
      final user = await _repo.getMe();
      state = AuthAuthenticated(user);
    } catch (_) {}
  }

  Future<void> logout() async {
    final refreshToken = await _storage.getRefreshToken();
    if (refreshToken != null) {
      try {
        await _repo.logout(refreshToken);
      } catch (_) {}
    }
    await _storage.clearSession();
    state = const AuthUnauthenticated();
  }

  void onSessionExpired() {
    _storage.clearSession();
    state = const AuthUnauthenticated();
  }
}

final StateNotifierProvider<AuthNotifier, AuthState> authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(
    ref.watch(authRepositoryProvider),
    ref.watch(secureStorageProvider),
  ),
);

final Provider<User?> currentUserProvider = Provider<User?>(
  (ref) {
    final s = ref.watch(authNotifierProvider);
    return s is AuthAuthenticated ? s.user : null;
  },
);