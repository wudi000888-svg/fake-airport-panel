import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


MODULES = [
    "panel_config",
    "json_store",
    "payments_store",
]


@pytest.fixture()
def payment_modules(tmp_path, monkeypatch):
    panel_dir = tmp_path / "panel"
    panel_dir.mkdir()
    monkeypatch.setenv("PANEL_DIR", str(panel_dir))
    for name in MODULES:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    return {name: sys.modules[name] for name in MODULES}


def test_payment_method_crud_and_user_visibility(payment_modules):
    store = payment_modules["payments_store"]
    method = store.upsert_method(
        {
            "id": "usdt-eth",
            "asset": "USDT",
            "chain": "ethereum",
            "address": "0x1111111111111111111111111111111111111111",
            "token_contract": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "decimals": "6",
            "rpc_url": "https://rpc.example",
            "confirmations_required": "12",
            "enabled": True,
        }
    )
    assert method["asset"] == "USDT"
    assert method["chain"] == "ethereum"
    assert method["enabled"] is True
    assert store.get_method("usdt-eth")["rpc_url"] == "https://rpc.example"
    assert store.list_methods(admin=False)[0]["id"] == "usdt-eth"
    assert "rpc_url" not in store.list_methods(admin=False)[0]

    store.set_method_enabled("usdt-eth", False)
    assert store.list_methods(admin=False) == []
    assert store.list_methods(admin=True)[0]["enabled"] is False


def test_payment_intent_creation_and_txid_uniqueness(payment_modules):
    store = payment_modules["payments_store"]
    payment = store.create_payment(
        {
            "order_id": "ord_1",
            "username": "alice",
            "method_id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "usd_amount": "39.00",
            "crypto_amount": "0.00039000",
            "rate_usd": "100000",
            "address": "bc1qexample",
            "qr_payload": "bitcoin:bc1qexample?amount=0.00039000",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    assert payment["id"].startswith("pay_")
    assert payment["status"] == "awaiting_payment"

    updated = store.attach_txid(payment["id"], "tx123")
    assert updated["txid"] == "tx123"
    other = store.create_payment(
        {
            "order_id": "ord_2",
            "username": "bob",
            "method_id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "usd_amount": "39.00",
            "crypto_amount": "0.00039000",
            "rate_usd": "100000",
            "address": "bc1qexample",
            "qr_payload": "bitcoin:bc1qexample?amount=0.00039000",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    with pytest.raises(RuntimeError, match="txid already used"):
        store.attach_txid(other["id"], "tx123")


def test_payment_public_helpers_update_kwargs_and_list_limit(payment_modules):
    store = payment_modules["payments_store"]
    method = {
        "id": "btc-main",
        "asset": "BTC",
        "chain": "bitcoin",
        "address": "bc1qexample",
        "btc_api_url": "https://btc-api.example",
        "enabled": True,
    }
    assert "btc_api_url" in store.public_method(method, admin=True)
    assert "btc_api_url" not in store.public_method(method, admin=False)

    first = store.create_payment(
        {
            "order_id": "ord_1",
            "username": "alice",
            "method_id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "usd_amount": "39.00",
            "crypto_amount": "0.00039000",
            "rate_usd": "100000",
            "address": "bc1qexample",
            "qr_payload": "bitcoin:bc1qexample?amount=0.00039000",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    second = store.create_payment(
        {
            "order_id": "ord_2",
            "username": "alice",
            "method_id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "usd_amount": "49.00",
            "crypto_amount": "0.00049000",
            "rate_usd": "100000",
            "address": "bc1qexample",
            "qr_payload": "bitcoin:bc1qexample?amount=0.00049000",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )

    updated = store.update_payment(
        first["id"],
        status="detected",
        detected_amount="0.00039000",
        internal_note="manual review",
    )
    assert updated["status"] == "detected"
    assert updated["detected_amount"] == "0.00039000"
    assert store.public_payment(updated, admin=True)["internal_note"] == "manual review"
    assert "internal_note" not in store.public_payment(updated, admin=False)

    public_items = store.list_payments(username="alice", admin=False, limit=1)
    assert len(public_items) == 1
    assert public_items[0]["id"] == first["id"]
    assert "internal_note" not in public_items[0]

    admin_items = store.list_payments(username="alice", admin=True, limit=2)
    assert [item["id"] for item in admin_items] == [first["id"], second["id"]]
    assert admin_items[0]["internal_note"] == "manual review"
