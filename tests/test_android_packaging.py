import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android-app"


class AndroidPackagingContractTests(unittest.TestCase):
    def read(self, relative):
        return (ANDROID / relative).read_text(encoding="utf-8")

    def test_android_81_minimum_and_both_arm_abis_are_declared(self):
        manifest = self.read("app/src/main/AndroidManifest.xml")
        gradle = self.read("app/build.gradle")
        self.assertIn('minSdk 27', gradle)
        self.assertIn('abiFilters "armeabi-v7a"', gradle)
        self.assertIn('abiFilters "arm64-v8a"', gradle)
        self.assertIn("com.chaquo.python.android.PyApplication", manifest)

    def test_each_abi_uses_a_compatible_python_and_network_stack(self):
        gradle = self.read("app/build.gradle")
        self.assertIn('version = "3.11"', gradle)
        self.assertIn('buildPython("python3.11")', gradle)
        self.assertIn('version = "3.13"', gradle)
        self.assertIn('buildPython("python3.13")', gradle)
        self.assertIn('install("curl_cffi==0.16.2")', gradle)
        self.assertIn('install("requests==2.32.5")', gradle)

    def test_embedded_services_bind_only_to_loopback_and_keep_data_private(self):
        launcher = self.read("app/src/main/python/android_entry.py")
        activity = self.read("app/src/main/java/com/dsh017/android/MainActivity.java")
        self.assertIn('host="127.0.0.1"', launcher)
        for port in ("8092", "8080", "8091", "8084"):
            self.assertIn(port, launcher)
        self.assertIn('setAllowFileAccess(false)', activity)
        self.assertIn('setAllowContentAccess(false)', activity)
        self.assertIn('"127.0.0.1".equals(host)', activity)
        self.assertIn("apiKeyStore.read()", activity)

    def test_provider_key_is_encrypted_by_android_keystore(self):
        store = self.read("app/src/main/java/com/dsh017/android/ApiKeyStore.java")
        self.assertIn('"AndroidKeyStore"', store)
        self.assertIn('"AES/GCM/NoPadding"', store)
        self.assertIn("KeyGenParameterSpec", store)

    def test_provider_credentials_use_keystore_and_are_loaded_by_embedded_runtime(self):
        store = self.read("app/src/main/java/com/dsh017/android/ApiKeyStore.java")
        activity = self.read("app/src/main/java/com/dsh017/android/MainActivity.java")
        launcher = self.read("app/src/main/python/android_entry.py")
        self.assertIn("readProviderKeysJson", store)
        self.assertIn("saveProviderKey", store)
        self.assertIn("JavascriptInterface", activity)
        self.assertIn("ProviderKeyBridge", activity)
        self.assertIn("provider_keys_json", launcher)
        self.assertIn("set_runtime_provider_secret", launcher)
        self.assertIn('page.startsWith("http://127.0.0.1:8092/providers")', activity)

    def test_ci_builds_both_installable_variants(self):
        workflow = (ROOT / ".github/workflows/android-apk.yml").read_text(encoding="utf-8")
        self.assertIn("assembleArm32Debug", workflow)
        self.assertIn("assembleArm64Debug", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)

    def test_release_build_requires_persistent_signing_and_checks_both_abis(self):
        gradle = self.read("app/build.gradle")
        workflow = (ROOT / ".github/workflows/android-apk.yml").read_text(encoding="utf-8")
        for secret in (
            "DSH017_ANDROID_KEYSTORE_PATH",
            "DSH017_ANDROID_STORE_PASSWORD",
            "DSH017_ANDROID_KEY_ALIAS",
            "DSH017_ANDROID_KEY_PASSWORD",
        ):
            self.assertIn(secret, gradle)
            self.assertIn(secret, workflow)
        self.assertIn("releaseBuildRequested", gradle)
        self.assertIn("throw new GradleException", gradle)
        self.assertIn("signingConfig signingConfigs.release", gradle)
        self.assertIn("assembleArm32Release", workflow)
        self.assertIn("assembleArm64Release", workflow)
        self.assertIn('/build-tools/35.0.0/apksigner" verify --print-certs', workflow)
        self.assertIn("ARM32_CERT", workflow)
        self.assertIn("ARM64_CERT", workflow)
        self.assertIn("SHA256SUMS.txt", workflow)
        self.assertIn("DSH017_ANDROID_KEYSTORE_BASE64", workflow)


if __name__ == "__main__":
    unittest.main()
