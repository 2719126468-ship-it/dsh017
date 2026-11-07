from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AndroidSafMigrationContractTests(unittest.TestCase):
    def test_activity_uses_storage_access_framework_without_broad_storage_permission(self):
        activity = (ROOT / "android-app/app/src/main/java/com/dsh017/android/MainActivity.java").read_text(encoding="utf-8")
        manifest = (ROOT / "android-app/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT", activity)
        self.assertIn("Intent.ACTION_CREATE_DOCUMENT", activity)
        self.assertIn("REQUEST_IMPORT_BACKUP", activity)
        self.assertIn("REQUEST_EXPORT_BACKUP", activity)
        self.assertIn("MAX_MIGRATION_ARCHIVE_BYTES", activity)
        self.assertIn("copyBounded", activity)
        self.assertNotIn("READ_EXTERNAL_STORAGE", manifest)
        self.assertNotIn("MANAGE_EXTERNAL_STORAGE", manifest)

    def test_restore_is_validated_before_embedded_services_start(self):
        activity = (ROOT / "android-app/app/src/main/java/com/dsh017/android/MainActivity.java").read_text(encoding="utf-8")
        restore_call = activity.index('"restore_backup_archive"')
        startup_status = activity.index('"备份已验证并恢复，正在启动内置服务')
        self.assertLess(restore_call, startup_status)
        self.assertIn("if (hasExistingDatabase()) startBackend();", activity)
        self.assertIn("showFirstRunMigrationDialog()", activity)
        self.assertIn("拒绝覆盖现有应用数据", activity)

    def test_embedded_python_packages_shared_backup_restore_implementation(self):
        gradle = (ROOT / "android-app/app/build.gradle").read_text(encoding="utf-8")
        entry = (ROOT / "android-app/app/src/main/python/android_entry.py").read_text(encoding="utf-8")
        backup = (ROOT / "scripts/data_backup.py").read_text(encoding="utf-8")
        self.assertIn('../scripts/data_backup.py', gradle)
        self.assertIn("def create_backup_archive", entry)
        self.assertIn("def restore_backup_archive", entry)
        self.assertIn('from data_backup import _backup', entry)
        self.assertIn('from data_backup import _restore', entry)
        self.assertIn("android_nested_presets", backup)
        self.assertIn('db_name="bili_data.db"', entry)

    def test_legacy_host_export_uses_run_as_and_shared_secret_excluding_archive(self):
        exporter = (ROOT / "scripts/export_legacy_android_backup.py").read_text(encoding="utf-8")
        backup = (ROOT / "scripts/data_backup.py").read_text(encoding="utf-8")
        self.assertIn('"exec-out", "run-as", package', exporter)
        self.assertIn('DEFAULT_PACKAGE = "com.dsh017.android.debug"', exporter)
        self.assertIn("from data_backup import _backup", exporter)
        self.assertIn('"provider_secrets.json"', backup)
        self.assertIn('"auth_token"', backup)
        self.assertIn('"admin_token"', backup)


if __name__ == "__main__":
    unittest.main()
