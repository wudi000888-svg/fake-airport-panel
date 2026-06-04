import importlib
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


def test_demo_viewer_login_user_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("PANEL_DIR", str(tmp_path / "panel"))
    monkeypatch.setenv("XRAY_CONFIG", str(tmp_path / "xray" / "config.json"))
    monkeypatch.setenv("HY2_ENV_FILE", str(tmp_path / "hysteria2" / ".env"))
    monkeypatch.setenv("HY2_CONFIG_FILE", str(tmp_path / "hysteria2" / "server.yaml"))

    for name in ["panel_config", "auth_store", "user_store", "docs.demo_data"]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    demo_data = importlib.import_module("docs.demo_data")
    demo_data.main()

    auth_store = importlib.reload(sys.modules["auth_store"])
    user_store = importlib.reload(sys.modules["user_store"])

    auth = auth_store.load_auth()
    users = user_store.load_users()["users"]
    demo_usernames = [
        username
        for username, item in auth.get("users", {}).items()
        if item.get("role") == "user"
    ]
    assert demo_usernames
    assert all(username in users for username in demo_usernames)
