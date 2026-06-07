import store_facade
from panel_config import DEFAULT_HY2_NAME, DEFAULT_VLESS_ADDRESS, DEFAULT_VLESS_NAME
from repositories.sqlite_settings import SQLiteSettingsRepository


def defaults():
    return {
        "vless_address": DEFAULT_VLESS_ADDRESS,
        "vless_port": 443,
        "vless_name": DEFAULT_VLESS_NAME,
        "hy2_name": DEFAULT_HY2_NAME,
    }


def read():
    store_facade.ensure_sqlite()
    data = defaults()
    data.update(SQLiteSettingsRepository().get("link_settings", {}))
    return data
