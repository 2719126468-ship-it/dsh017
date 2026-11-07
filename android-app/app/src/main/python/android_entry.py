"""Embedded DSH017 backend launcher used by the Android WebView APK."""
import os
import threading
import time
from urllib.request import urlopen

_started = False
_start_lock = threading.Lock()
_errors = {}
_apps = ()


def _serve(label, flask_app, port, threads):
    from waitress import serve
    try:
        serve(
            flask_app,
            host="127.0.0.1",
            port=port,
            threads=threads,
            channel_timeout=90,
            connection_limit=40,
        )
    except Exception as exc:
        _errors[label] = "%s: %s" % (type(exc).__name__, str(exc)[:240])
        print("[DSH017 Android] %s stopped: %s" % (label, _errors[label]))


def start_services(data_dir, preset_dir, api_key="", provider_keys_json="{}"):
    """Configure private storage, import the app, and launch all local services."""
    global _started, _apps
    with _start_lock:
        if _started:
            set_api_key(api_key)
            return True

        data_dir = os.path.abspath(data_dir)
        preset_dir = os.path.abspath(preset_dir)
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(preset_dir, exist_ok=True)
        os.environ["HOME"] = data_dir
        os.environ["DSH017_ANDROID_MODE"] = "1"
        os.environ["DSH017_DATA_DIR"] = data_dir
        os.environ["DSH017_DB_PATH"] = os.path.join(data_dir, "bili_data.db")
        os.environ["DSH017_BACKUP_DIR"] = os.path.join(data_dir, "backup")
        os.environ["DSH017_PRESET_DIR"] = preset_dir
        os.environ["DSH017_NOVEL_CHARSET_PATH"] = os.path.join(data_dir, "novel_charset.json")
        if api_key:
            os.environ["ZHIPU_API_KEY"] = api_key
        else:
            os.environ.pop("ZHIPU_API_KEY", None)

        # Import only after paths and credentials are configured.
        try:
            import json
            provider_keys = json.loads(provider_keys_json or "{}")
            if not isinstance(provider_keys, dict):
                provider_keys = {}
        except (TypeError, ValueError):
            provider_keys = {}

        # Import only after paths and the API key are configured.
        from app.providers import set_runtime_provider_secret
        for provider_id, secret in provider_keys.items():
            if isinstance(provider_id, str) and isinstance(secret, str):
                set_runtime_provider_secret(provider_id, secret)

        from bili_console import app as bili_app
        from hub_server import app as hub_app
        from novel_server import app as novel_app
        from tarot_server import app as tarot_app

        _apps = (bili_app, hub_app, novel_app, tarot_app)
        services = (
            ("bilibili", bili_app, 8092, 3),
            ("hub", hub_app, 8080, 2),
            ("novel", novel_app, 8091, 2),
            ("tarot", tarot_app, 8084, 2),
        )
        for label, flask_app, port, threads in services:
            worker = threading.Thread(
                target=_serve,
                args=(label, flask_app, port, threads),
                name="dsh017-" + label,
                daemon=True,
            )
            worker.start()

        _started = True
        return True


def set_api_key(api_key):
    """Update the in-memory provider key without exposing it to WebView JavaScript."""
    value = str(api_key or "").strip()
    if value:
        os.environ["ZHIPU_API_KEY"] = value
    else:
        os.environ.pop("ZHIPU_API_KEY", None)

    try:
        import app.llm_config as llm_config
        llm_config.ZHIPU_API_KEY = value
    except Exception:
        pass
    for module_name in ("app.chat_ui", "app.chat_routes"):
        try:
            module = __import__(module_name, fromlist=["ZHIPU_API_KEY"])
            module.ZHIPU_API_KEY = value
        except Exception:
            pass
    return True


def wait_ready(timeout_seconds=45):
    """Wait until all four local Flask applications answer their health routes."""
    ports = (8092, 8080, 8091, 8084)
    deadline = time.time() + max(5, min(int(timeout_seconds), 120))
    while time.time() < deadline:
        ready = True
        for port in ports:
            try:
                with urlopen("http://127.0.0.1:%d/health" % port, timeout=1.5) as response:
                    if response.status < 200 or response.status >= 300:
                        ready = False
                        break
            except Exception:
                ready = False
                break
        if ready:
            return True
        time.sleep(0.35)
    return False



def create_backup_archive(output_dir, data_dir, preset_dir):
    """Create an archive from the Android app's explicit private storage paths."""
    from argparse import Namespace
    from data_backup import _backup
    data_dir = os.path.abspath(data_dir)
    preset_dir = os.path.abspath(preset_dir)
    return str(_backup(Namespace(
        data_dir=data_dir,
        db_path=os.path.join(data_dir, "bili_data.db"),
        preset_dir=preset_dir,
        backup_dir=output_dir,
    )))


def restore_backup_archive(archive_path, data_dir, preset_dir):
    """Validate and restore a user-selected archive before services are started."""
    from argparse import Namespace
    from data_backup import _restore
    restored_data, restored_presets = _restore(Namespace(
        archive=archive_path,
        data_dir=data_dir,
        preset_dir=preset_dir,
        db_name="bili_data.db",
    ))
    return {"data_dir": str(restored_data), "preset_dir": str(restored_presets)}

def startup_errors():
    return dict(_errors)


def set_provider_key(provider_id, api_key):
    """Receive a credential already encrypted by the Android Keystore bridge."""
    try:
        from app.providers import set_runtime_provider_secret
        return set_runtime_provider_secret(str(provider_id), str(api_key or ""))
    except Exception:
        return False
