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

The APK does not contain an API key. Tap **API 设置** in the top bar and enter your own Zhipu API key. The key is encrypted with Android Keystore and is never exposed to page JavaScript. Bilibili, novel and tarot pages can open without an AI key, subject to the upstream sites' current behavior.

## ARM-specific network behavior

The 64-bit build uses the Android ARM64 wheel of `curl_cffi` (from the Flet Android wheel index) to retain browser TLS impersonation.

The ARMv7 build uses the project's `requests` fallback because there is no compatible 32-bit ARM Android `curl_cffi` wheel in that distribution. Bilibili and novel endpoints which rely on browser TLS fingerprinting may therefore be less reliable on 32-bit devices. This is an upstream binary-wheel limitation, not a UI restriction.

## Build

Run from the repository root with JDK 17, Android SDK 35, Gradle 8.13 and the matching Python version:

```bash
# 32-bit ARM
python3.11 --version
gradle -p android-app assembleArm32Debug

# 64-bit ARM
python3.12 --version
gradle -p android-app assembleArm64Debug
```

The GitHub Actions workflow builds both variants and publishes separate installable APK artifacts for 30 days. These are debug-signed sideload builds, not Play Store release builds.
