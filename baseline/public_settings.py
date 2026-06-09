import store_facade
from repositories.sqlite_settings import SQLiteSettingsRepository


DEFAULTS = {
    "registration_enabled": False,
}


def read():
    store_facade.ensure_sqlite()
    data = dict(DEFAULTS)
    saved = SQLiteSettingsRepository().get("public_settings", {})
    if isinstance(saved, dict):
        data.update(saved)
    data["registration_enabled"] = bool(data.get("registration_enabled", False))
    return data


def update(data):
    store_facade.ensure_sqlite()
    current = read()
    if "registration_enabled" in (data or {}):
        value = data.get("registration_enabled")
        if isinstance(value, str):
            value = value.lower() in {"1", "true", "yes", "y", "on"}
        current["registration_enabled"] = bool(value)
    SQLiteSettingsRepository().set("public_settings", current)
    return current
