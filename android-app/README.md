# DSH017 Android APK

This is a self-contained Android shell around the existing DSH017 web application. It embeds the Flask services with Chaquopy and displays the local service pages in Android WebView; it does not require Termux or proot.

## Device compatibility

- Minimum Android: 8.1 (API 27).
- Build outputs are separate APKs for `armeabi-v7a` (32-bit ARM) and `arm64-v8a` (64-bit ARM).
- Keep Android System WebView or Chrome enabled and updated. The APK uses the system WebView engine.
- Install only the APK matching the device architecture. Both builds use the same application ID and app data layout.

## What starts locally

The app starts four Flask services bound to loopback only:

| Service | Local port |
|---|---:|
| Bilibili / Chat / Workspace / Shorts | 8092 |
| Unified service hub | 8080 |
| Novel reader | 8091 |
| Tarot | 8084 |

SQLite, chat history, presets, backups and the optional novel charset are stored in the app's private files directory. The embedded server is not exposed to the LAN.

## AI key

The APK does not contain any provider key. Tap **API 设置** in the top bar to enter your own Zhipu API key. Additional OpenAI-compatible providers are configured from the **模型供应商** page. Provider keys are encrypted with Android Keystore and are never exposed to page JavaScript. The Magpie local app identifier is stored through the same encrypted bridge; Magpie itself must be installed and signed in separately, with its Gateway running on the device at `127.0.0.1:3425` for automatic discovery. Bilibili, novel and tarot pages can open without an AI key, subject to the upstream sites' current behavior.

## ARM-specific network behavior

The 64-bit build uses the Android ARM64 wheel of `curl_cffi` (from the Flet Android wheel index) to retain browser TLS impersonation.

The ARMv7 build uses the project's `requests` fallback because there is no compatible 32-bit ARM Android `curl_cffi` wheel in that distribution. Bilibili and novel endpoints which rely on browser TLS fingerprinting may therefore be less reliable on 32-bit devices. This is an upstream binary-wheel limitation, not a UI restriction.

## CI builds and versioned releases

Pull requests, branch pushes and manual CI runs build **debug** APKs for ARMv7 and ARM64. Those are test artifacts retained by GitHub Actions for 30 days. They use the Android debug signing identity and the debug application ID suffix; do not treat them as upgrade-compatible release APKs.

A push of a `v*` tag runs the separate **Release** build for both ABIs. Release APKs are signed with one persistent keystore, and the publish job verifies that both APKs have the same signer certificate SHA-256 fingerprint before creating the GitHub Release. The release includes both APKs, `SHA256SUMS.txt`, and `SIGNING_CERT_SHA256.txt`. If signing secrets are missing or invalid, the Release build fails closed and does not fall back to a temporary debug key.

### Configure the persistent release signing key

Generate the keystore locally and keep a secure offline backup. Never commit the keystore or share its passwords in Issues, chat, or logs.

```bash
keytool -genkeypair -v -keystore dsh017-release.jks \
  -alias dsh017-release -keyalg RSA -keysize 3072 -validity 10000
base64 -w 0 dsh017-release.jks
```

In the repository's **Settings → Secrets and variables → Actions**, create these repository secrets:

- `DSH017_ANDROID_KEYSTORE_BASE64`: the base64 output of the keystore file.
- `DSH017_ANDROID_STORE_PASSWORD`: keystore password.
- `DSH017_ANDROID_KEY_ALIAS`: `dsh017-release` (or the alias you created).
- `DSH017_ANDROID_KEY_PASSWORD`: key password.

Do not rotate or replace this signing identity for ordinary releases. Losing it prevents Android from accepting an in-place update signed by the same application identity. Keep the offline keystore backup and recovery information separate from the repository.

The tagged Release workflow does not publish debug APKs. It requires all four secrets, validates the keystore and alias, signs both ABI variants, and checks that their signing certificate fingerprints match. A successful signed build still does not replace installation and upgrade testing on real devices.
