import json
import os
import re
import tempfile
from pathlib import Path


def get_settings_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "MSB Recorder" / "settings.json"


def load_settings(default_settings, default_include_states):
    settings_path = get_settings_path()
    if not settings_path.exists():
        return default_settings.copy(), default_include_states.copy()

    try:
        with settings_path.open("r", encoding="utf-8") as settings_file:
            saved = json.load(settings_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not load settings from {settings_path}: {error}"
        ) from error

    if not isinstance(saved, dict):
        raise RuntimeError(f"Settings file has an invalid format: {settings_path}")

    settings = default_settings.copy()
    saved_settings = saved.get("settings", {})
    if isinstance(saved_settings, dict):
        for key, default in default_settings.items():
            value = saved_settings.get(key, default)
            if key == "Webcam Position":
                value = {"Left": "Top Left", "Right": "Top Right"}.get(
                    value, value
                )
            if isinstance(default, dict):
                if isinstance(value, dict):
                    settings[key] = {
                        name: shortcut
                        for name, shortcut in value.items()
                        if name in default and isinstance(shortcut, str)
                    } | {
                        name: shortcut
                        for name, shortcut in default.items()
                        if name not in value
                    }
            elif key == "Resolution" and (
                not isinstance(value, str)
                or value not in {
                    "1920 x 1080 (Full HD)",
                    "1280 x 720 (HD)",
                    "3840 x 2160 (4K)",
                }
            ):
                continue
            elif key == "Frame Rate" and (
                not isinstance(value, str) or value not in {"60 FPS", "30 FPS"}
            ):
                continue
            elif key == "Quality" and (
                not isinstance(value, str)
                or value not in {"High", "Ultra Lossless", "Medium"}
            ):
                continue
            elif key == "Output Format" and (
                not isinstance(value, str)
                or value not in {"MP4 (Recommended)", "MKV", "AVI"}
            ):
                continue
            elif key == "Screenshot Format" and (
                not isinstance(value, str) or value not in {"PNG", "JPEG"}
            ):
                continue
            elif key == "Key Overlay Position" and (
                not isinstance(value, str)
                or value not in {"Left", "Center", "Right"}
            ):
                continue
            elif key == "Webcam Position" and (
                not isinstance(value, str)
                or value not in {
                    "Left",
                    "Right",
                    "Top Left",
                    "Top Right",
                    "Bottom Left",
                    "Bottom Right",
                }
            ):
                continue
            elif key == "Key Overlay Size" and (
                not isinstance(value, str)
                or value not in {"Small", "Medium", "Large"}
            ):
                continue
            elif key == "Key Overlay Key Type" and (
                not isinstance(value, str)
                or value not in {"All Keys", "Special Keys"}
            ):
                continue
            elif key == "Key Overlay Color" and (
                not isinstance(value, str)
                or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value)
            ):
                continue
            elif isinstance(value, type(default)) or (
                default is None and isinstance(value, (str, type(None)))
            ):
                settings[key] = value

    include_states = default_include_states.copy()
    saved_include_states = saved.get("include_states", {})
    if isinstance(saved_include_states, dict):
        for key in include_states:
            value = saved_include_states.get(key)
            if isinstance(value, bool):
                include_states[key] = value

    return settings, include_states


def save_settings(settings, include_states):
    settings_path = get_settings_path()
    temporary_path = None
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=settings_path.parent,
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as settings_file:
            temporary_path = Path(settings_file.name)
            json.dump(
                {
                    "settings": settings,
                    "include_states": include_states,
                },
                settings_file,
                indent=2,
            )
            settings_file.write("\n")
            settings_file.flush()
            os.fsync(settings_file.fileno())
        os.replace(temporary_path, settings_path)
    except (OSError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"Could not save settings to {settings_path}: {error}"
        ) from error
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
