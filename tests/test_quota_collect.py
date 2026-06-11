import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


def test_xray_node_deltas_initializes_node_baseline_for_upgraded_users(monkeypatch):
    import quota_collect

    user = {"last_xray_stats": {"uplink": 1200, "downlink": 3400}}
    nodes = [{"id": "vless-main"}, {"id": "vless-proxy-1"}]
    stats = {
        "user>>>alice>>>traffic>>>uplink": 1000,
        "user>>>alice>>>traffic>>>downlink": 3000,
        "user>>>alice.vless-proxy-1>>>traffic>>>uplink": 200,
        "user>>>alice.vless-proxy-1>>>traffic>>>downlink": 400,
    }

    monkeypatch.setattr(quota_collect.node_catalog, "nodes_for_user", lambda user, kind, include_disabled: nodes)
    monkeypatch.setattr(
        quota_collect.node_catalog,
        "vless_node_email",
        lambda username, node_id: username if node_id == "vless-main" else f"{username}.{node_id}",
    )

    samples = quota_collect.xray_node_deltas(stats, "alice", user)

    assert samples == []
    assert user["last_node_stats"] == {
        "xray:vless-main": {"uplink": 1000, "downlink": 3000},
        "xray:vless-proxy-1": {"uplink": 200, "downlink": 400},
    }


def test_xray_node_deltas_records_incremental_node_samples(monkeypatch):
    import quota_collect

    user = {
        "last_xray_stats": {"uplink": 1200, "downlink": 3400},
        "last_node_stats": {
            "xray:vless-main": {"uplink": 1000, "downlink": 3000},
            "xray:vless-proxy-1": {"uplink": 200, "downlink": 400},
        },
    }
    nodes = [{"id": "vless-main"}, {"id": "vless-proxy-1"}]
    stats = {
        "user>>>alice>>>traffic>>>uplink": 1500,
        "user>>>alice>>>traffic>>>downlink": 3100,
        "user>>>alice.vless-proxy-1>>>traffic>>>uplink": 250,
        "user>>>alice.vless-proxy-1>>>traffic>>>downlink": 900,
    }

    monkeypatch.setattr(quota_collect.node_catalog, "nodes_for_user", lambda user, kind, include_disabled: nodes)
    monkeypatch.setattr(
        quota_collect.node_catalog,
        "vless_node_email",
        lambda username, node_id: username if node_id == "vless-main" else f"{username}.{node_id}",
    )

    assert quota_collect.xray_node_deltas(stats, "alice", user) == [
        {
            "username": "alice",
            "source": "xray",
            "node_id": "vless-main",
            "uplink_bytes": 500,
            "downlink_bytes": 100,
        },
        {
            "username": "alice",
            "source": "xray",
            "node_id": "vless-proxy-1",
            "uplink_bytes": 50,
            "downlink_bytes": 500,
        },
    ]


def test_xray_node_deltas_keeps_existing_baseline_when_counters_are_missing(monkeypatch):
    import quota_collect

    user = {
        "last_node_stats": {
            "xray:vless-main": {"uplink": 1000, "downlink": 3000},
        },
    }
    nodes = [{"id": "vless-main"}]
    stats = {"user>>>someone-else>>>traffic>>>uplink": 1}

    monkeypatch.setattr(quota_collect.node_catalog, "nodes_for_user", lambda user, kind, include_disabled: nodes)
    monkeypatch.setattr(quota_collect.node_catalog, "vless_node_email", lambda username, node_id: username)

    assert quota_collect.xray_node_deltas(stats, "alice", user) == []
    assert user["last_node_stats"]["xray:vless-main"] == {"uplink": 1000, "downlink": 3000}


def test_quota_collect_keeps_existing_baselines_when_stats_are_unavailable(monkeypatch):
    import quota_collect

    data = {
        "users": {
            "alice": {
                "enabled": True,
                "used_bytes": 1234,
                "quota_bytes": 10_000,
                "quota_exceeded": False,
                "last_xray_stats": {"uplink": 500, "downlink": 700},
                "last_hy2_stats": {"tx": 100, "rx": 200},
                "last_node_stats": {"xray:vless-main": {"uplink": 500, "downlink": 700}},
            }
        }
    }
    saved = []

    monkeypatch.setattr(quota_collect, "RETENTION_DAYS", 0)
    monkeypatch.setattr(quota_collect.user_store, "load_users", lambda: data)
    monkeypatch.setattr(quota_collect.user_store, "save_users", lambda item: saved.append(item))
    monkeypatch.setattr(quota_collect, "query_xray_stats", lambda: {})
    monkeypatch.setattr(quota_collect, "query_hy2_stats", lambda: {})
    monkeypatch.setattr(quota_collect.node_catalog, "nodes_for_user", lambda user, kind, include_disabled: [{"id": "vless-main"}])
    monkeypatch.setattr(quota_collect.node_catalog, "vless_node_email", lambda username, node_id: username)
    monkeypatch.setattr(quota_collect.traffic_store, "add_sample", lambda sample: (_ for _ in ()).throw(AssertionError("unexpected sample")))

    quota_collect.main()

    assert saved == []
    assert data["users"]["alice"]["used_bytes"] == 1234
    assert data["users"]["alice"]["last_xray_stats"] == {"uplink": 500, "downlink": 700}
    assert data["users"]["alice"]["last_hy2_stats"] == {"tx": 100, "rx": 200}
    assert data["users"]["alice"]["last_node_stats"]["xray:vless-main"] == {"uplink": 500, "downlink": 700}


def test_quota_collect_skips_missing_hy2_user_without_resetting_baseline(monkeypatch):
    import quota_collect

    data = {
        "users": {
            "alice": {
                "enabled": True,
                "used_bytes": 1234,
                "quota_bytes": 10_000,
                "quota_exceeded": False,
                "last_xray_stats": {"uplink": 0, "downlink": 0},
                "last_hy2_stats": {"tx": 100, "rx": 200},
            }
        }
    }
    saved = []

    monkeypatch.setattr(quota_collect, "RETENTION_DAYS", 0)
    monkeypatch.setattr(quota_collect.user_store, "load_users", lambda: data)
    monkeypatch.setattr(quota_collect.user_store, "save_users", lambda item: saved.append(item))
    monkeypatch.setattr(quota_collect, "query_xray_stats", lambda: {"user>>>someone-else>>>traffic>>>uplink": 1})
    monkeypatch.setattr(quota_collect, "query_hy2_stats", lambda: {"someone-else": {"tx": 1, "rx": 1}})
    monkeypatch.setattr(quota_collect.node_catalog, "nodes_for_user", lambda user, kind, include_disabled: [{"id": "vless-main"}])
    monkeypatch.setattr(quota_collect.node_catalog, "vless_node_email", lambda username, node_id: username)
    monkeypatch.setattr(quota_collect.traffic_store, "add_sample", lambda sample: (_ for _ in ()).throw(AssertionError("unexpected sample")))

    quota_collect.main()

    assert saved == []
    assert data["users"]["alice"]["used_bytes"] == 1234
    assert data["users"]["alice"]["last_hy2_stats"] == {"tx": 100, "rx": 200}


def test_quota_collect_prunes_old_traffic_samples(monkeypatch):
    import quota_collect

    pruned = []
    monkeypatch.setattr(quota_collect, "RETENTION_DAYS", 30)
    monkeypatch.setattr(quota_collect.user_store, "load_users", lambda: {"users": {}})
    monkeypatch.setattr(quota_collect.user_store, "save_users", lambda data: None)
    monkeypatch.setattr(quota_collect, "query_xray_stats", lambda: {})
    monkeypatch.setattr(quota_collect, "query_hy2_stats", lambda: {})
    monkeypatch.setattr(quota_collect.traffic_store, "delete_before", lambda cutoff: pruned.append(cutoff) or 2)

    quota_collect.main()

    assert len(pruned) == 1
    assert pruned[0].endswith("+00:00")
