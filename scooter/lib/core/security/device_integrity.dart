import 'package:safe_device/safe_device.dart';

/// Best-effort root/jailbreak check, run once at splash startup. Fails
/// open on a plugin error (unsupported platform, emulator quirks) — a
/// broken detector should never brick the app for legitimate users; a
/// genuinely rooted/jailbroken device still gets caught on the happy path.
Future<bool> isDeviceCompromised() async {
  try {
    return await SafeDevice.isJailBroken;
  } catch (_) {
    return false;
  }
}
