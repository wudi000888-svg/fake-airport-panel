# Crypto Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add receive-only cryptocurrency payments for USD-priced orders, supporting USDT/USDC on Ethereum and BSC, ETH, BNB, and BTC, with chain verification and automatic order confirmation.

**Architecture:** Add an independent payments module backed by `payments.json`, linked to existing orders by `order_id`. Keep existing order statuses intact and add separate payment states. Verification is txid-based: users submit txid, backend verifies via configured EVM RPC or BTC public API, then calls the existing order confirmation flow.

**Tech Stack:** Python standard library HTTP server and JSON persistence, existing frontend SPA in `baseline/frontend/assets/app.js`, pytest, mocked RPC/API responses.

---

## File Structure

| Path | Responsibility |
|---|---|
| `baseline/panel_config.py` | Add `PAYMENTS_FILE` path. |
| `baseline/payments_store.py` | Persist payment methods, payment intents, rates, txid uniqueness, and public/admin views. |
| `baseline/payment_rates.py` | Decimal-safe USD-to-crypto rate handling, stablecoin defaults, admin overrides, cached automatic rates. |
| `baseline/payment_wallets.py` | Validate method asset/chain/address/endpoint/confirmation config and build QR payloads. |
| `baseline/payment_verifier.py` | Parse and verify EVM native txs, EVM ERC20 Transfer logs, and BTC tx API payloads. |
| `baseline/payment_service.py` | Create payment intents, attach txid, run verification, update payment state, and confirm orders. |
| `baseline/api_payment_routes.py` | GET/POST payment APIs with user/admin scoping. |
| `baseline/api_get_routes.py` | Route `GET /api/payment-methods` and `GET /api/payments`. |
| `baseline/api_post_routes.py` | Allow user-owned order/payment POST routes before the admin gate. |
| `baseline/api_user_routes.py` | Keep order creation route usable for normal users. |
| `baseline/dashboard_service.py` | Include payment methods and payments in dashboard payloads. |
| `baseline/backup_manager.py` | Include `payments.json` in backups. |
| `baseline/frontend/assets/app.js` | Add payment method UI, pay buttons, payment detail panel, txid submit, admin config and refresh actions. |
| `baseline/frontend/assets/style.css` | Add compact payment-specific layout styles. |
| `tests/test_crypto_payments.py` | Focused tests for stores, rates, verifiers, APIs, and order confirmation integration. |
| `tests/test_core_api.py` | Add module reload entries and regression for user order/payment POST permissions if needed. |
| `README.md` | Add short receive-only crypto payment note after implementation passes. |

---

### Task 1: Payment Config And Store

**Files:**
- Modify: `baseline/panel_config.py`
- Create: `baseline/payments_store.py`
- Test: `tests/test_crypto_payments.py`

- [ ] **Step 1: Write failing store tests**

Add `tests/test_crypto_payments.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: FAIL because `payments_store` does not exist.

- [ ] **Step 3: Add config path**

In `baseline/panel_config.py`, add next to `ORDERS_FILE`:

```python
PAYMENTS_FILE = PANEL_DIR / "payments.json"
```

- [ ] **Step 4: Implement payment store**

Create `baseline/payments_store.py`:

```python
import secrets
from datetime import datetime, timezone

from json_store import load_json, save_json
from panel_config import PAYMENTS_FILE


PUBLIC_METHOD_KEYS = {
    "id",
    "asset",
    "chain",
    "address",
    "decimals",
    "confirmations_required",
    "enabled",
    "label",
}

PUBLIC_PAYMENT_KEYS = {
    "id",
    "order_id",
    "username",
    "method_id",
    "asset",
    "chain",
    "usd_amount",
    "crypto_amount",
    "rate_usd",
    "address",
    "qr_payload",
    "status",
    "txid",
    "confirmations",
    "detected_amount",
    "expires_at",
    "created_at",
    "updated_at",
    "error",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_data():
    return {"version": 1, "methods": [], "payments": [], "rates": {"overrides": {}, "cache": {}}}


def load_payments():
    data = load_json(PAYMENTS_FILE, default_data, create=True)
    data.setdefault("version", 1)
    data.setdefault("methods", [])
    data.setdefault("payments", [])
    data.setdefault("rates", {"overrides": {}, "cache": {}})
    data["rates"].setdefault("overrides", {})
    data["rates"].setdefault("cache", {})
    return data


def save_payments(data):
    save_json(PAYMENTS_FILE, data)


def public_method(method, admin=False):
    if admin:
        item = dict(method)
    else:
        item = {k: method.get(k) for k in PUBLIC_METHOD_KEYS if k in method}
    return item


def public_payment(payment, admin=False):
    if admin:
        return dict(payment)
    return {k: payment.get(k) for k in PUBLIC_PAYMENT_KEYS if k in payment}


def list_methods(admin=False):
    methods = load_payments().get("methods", [])
    if not admin:
        methods = [m for m in methods if m.get("enabled", True)]
    return [public_method(m, admin=admin) for m in sorted(methods, key=lambda m: (m.get("sort", 100), m.get("id", "")))]


def get_method(method_id):
    for method in load_payments().get("methods", []):
        if method.get("id") == method_id:
            return method
    return None


def normalize_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off")


def upsert_method(data):
    method_id = str(data.get("id") or "").strip().lower()
    if not method_id:
        method_id = "pm_" + secrets.token_hex(4)
    method = {
        "id": method_id,
        "label": str(data.get("label") or method_id).strip(),
        "asset": str(data.get("asset") or "").strip().upper(),
        "chain": str(data.get("chain") or "").strip().lower(),
        "address": str(data.get("address") or "").strip(),
        "token_contract": str(data.get("token_contract") or "").strip(),
        "decimals": int(data.get("decimals", 18) or 18),
        "rpc_url": str(data.get("rpc_url") or "").strip(),
        "btc_api_url": str(data.get("btc_api_url") or "").strip(),
        "confirmations_required": int(data.get("confirmations_required", 12) or 12),
        "enabled": normalize_bool(data.get("enabled", True), True),
        "sort": int(data.get("sort", 100) or 100),
        "updated_at": now_iso(),
    }
    store = load_payments()
    methods = store.setdefault("methods", [])
    for idx, existing in enumerate(methods):
        if existing.get("id") == method_id:
            created_at = existing.get("created_at")
            methods[idx] = {**existing, **method}
            if created_at:
                methods[idx]["created_at"] = created_at
            break
    else:
        method["created_at"] = now_iso()
        methods.append(method)
    save_payments(store)
    return method


def set_method_enabled(method_id, enabled):
    store = load_payments()
    for method in store.get("methods", []):
        if method.get("id") == method_id:
            method["enabled"] = bool(enabled)
            method["updated_at"] = now_iso()
            save_payments(store)
            return method
    raise RuntimeError("payment method not found")


def delete_method(method_id):
    store = load_payments()
    old = len(store.get("methods", []))
    store["methods"] = [m for m in store.get("methods", []) if m.get("id") != method_id]
    if len(store["methods"]) == old:
        raise RuntimeError("payment method not found")
    save_payments(store)
    return True


def list_payments(username=None, admin=False, limit=200):
    payments = load_payments().get("payments", [])
    if username:
        payments = [p for p in payments if p.get("username") == username]
    payments = sorted(payments, key=lambda p: p.get("created_at", ""), reverse=True)
    return [public_payment(p, admin=admin) for p in payments[: int(limit or 200)]]


def get_payment(payment_id):
    for payment in load_payments().get("payments", []):
        if payment.get("id") == payment_id:
            return payment
    return None


def txid_used(txid, exclude_payment_id=""):
    txid = str(txid or "").strip()
    if not txid:
        return False
    for payment in load_payments().get("payments", []):
        if payment.get("id") != exclude_payment_id and str(payment.get("txid") or "").lower() == txid.lower():
            return True
    return False


def create_payment(fields):
    payment = {
        "id": "pay_" + secrets.token_hex(8),
        "status": "awaiting_payment",
        "confirmations": 0,
        "detected_amount": "",
        "txid": "",
        "error": "",
        "created_at": now_iso(),
        **fields,
    }
    store = load_payments()
    store.setdefault("payments", []).append(payment)
    save_payments(store)
    return payment


def update_payment(payment_id, **updates):
    store = load_payments()
    for payment in store.get("payments", []):
        if payment.get("id") == payment_id:
            payment.update(updates)
            payment["updated_at"] = now_iso()
            save_payments(store)
            return payment
    raise RuntimeError("payment not found")


def attach_txid(payment_id, txid):
    txid = str(txid or "").strip()
    if not txid:
        raise RuntimeError("txid is required")
    if txid_used(txid, exclude_payment_id=payment_id):
        raise RuntimeError("txid already used")
    return update_payment(payment_id, txid=txid, error="")


def save_rates(rates):
    store = load_payments()
    store["rates"] = rates
    save_payments(store)
    return store["rates"]


def load_rates():
    return load_payments().get("rates", {"overrides": {}, "cache": {}})
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/panel_config.py baseline/payments_store.py tests/test_crypto_payments.py
git commit -m "feat: add crypto payment store"
```

---

### Task 2: Wallet Method Validation And QR Payloads

**Files:**
- Create: `baseline/payment_wallets.py`
- Modify: `baseline/payments_store.py`
- Test: `tests/test_crypto_payments.py`

- [ ] **Step 1: Add failing wallet validation tests**

Append to `tests/test_crypto_payments.py`:

```python
def test_payment_method_validation_and_qr_payloads(payment_modules):
    payment_wallets = importlib.import_module("payment_wallets")

    evm = payment_wallets.normalize_method(
        {
            "id": "eth-main",
            "asset": "ETH",
            "chain": "ethereum",
            "address": "0x2222222222222222222222222222222222222222",
            "rpc_url": "https://rpc.example",
            "confirmations_required": "12",
        }
    )
    assert evm["decimals"] == 18
    assert payment_wallets.qr_payload(evm, "0.010000000000000000") == "ethereum:0x2222222222222222222222222222222222222222?value=0.010000000000000000"

    btc = payment_wallets.normalize_method(
        {
            "id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "address": "bc1qexample",
            "btc_api_url": "https://blockstream.info/api",
            "confirmations_required": "3",
        }
    )
    assert btc["decimals"] == 8
    assert payment_wallets.qr_payload(btc, "0.00039000") == "bitcoin:bc1qexample?amount=0.00039000"

    with pytest.raises(RuntimeError, match="token contract"):
        payment_wallets.normalize_method(
            {
                "id": "bad-usdt",
                "asset": "USDT",
                "chain": "ethereum",
                "address": "0x2222222222222222222222222222222222222222",
                "rpc_url": "https://rpc.example",
            }
        )
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_payment_method_validation_and_qr_payloads -q
```

Expected: FAIL because `payment_wallets` does not exist.

- [ ] **Step 3: Implement wallet helpers**

Create `baseline/payment_wallets.py`:

```python
import re


STABLE_ASSETS = {"USDT", "USDC"}
NATIVE_ASSETS = {"ETH", "BNB", "BTC"}
SUPPORTED = {
    ("USDT", "ethereum"),
    ("USDC", "ethereum"),
    ("USDT", "bsc"),
    ("USDC", "bsc"),
    ("ETH", "ethereum"),
    ("BNB", "bsc"),
    ("BTC", "bitcoin"),
}


def is_evm_chain(chain):
    return chain in ("ethereum", "bsc")


def normalize_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off")


def clean_id(value):
    raw = str(value or "").strip().lower()
    return "".join(ch for ch in raw.replace(" ", "-") if ch.isalnum() or ch in "-_")


def validate_evm_address(address, field="address"):
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", str(address or "").strip()):
        raise RuntimeError(f"{field} must be a 0x EVM address")


def normalize_method(data):
    asset = str(data.get("asset") or "").strip().upper()
    chain = str(data.get("chain") or "").strip().lower()
    if (asset, chain) not in SUPPORTED:
        raise RuntimeError("unsupported payment asset or chain")
    address = str(data.get("address") or "").strip()
    if not address:
        raise RuntimeError("receiving address is required")
    if is_evm_chain(chain):
        validate_evm_address(address)
    token_contract = str(data.get("token_contract") or "").strip()
    if asset in STABLE_ASSETS:
        if not token_contract:
            raise RuntimeError("token contract is required")
        validate_evm_address(token_contract, "token contract")
    rpc_url = str(data.get("rpc_url") or "").strip()
    btc_api_url = str(data.get("btc_api_url") or "").strip()
    if is_evm_chain(chain) and not rpc_url:
        raise RuntimeError("rpc url is required")
    if chain == "bitcoin" and not btc_api_url:
        raise RuntimeError("btc api url is required")
    default_decimals = 8 if asset == "BTC" else (18 if asset in ("ETH", "BNB") else 6)
    confirmations = int(data.get("confirmations_required", 12 if chain != "bitcoin" else 3) or 0)
    if confirmations <= 0:
        raise RuntimeError("confirmations must be greater than 0")
    method_id = clean_id(data.get("id") or f"{asset}-{chain}")
    if not method_id:
        raise RuntimeError("method id is required")
    return {
        "id": method_id,
        "label": str(data.get("label") or f"{asset} / {chain}").strip(),
        "asset": asset,
        "chain": chain,
        "address": address,
        "token_contract": token_contract,
        "decimals": int(data.get("decimals", default_decimals) or default_decimals),
        "rpc_url": rpc_url,
        "btc_api_url": btc_api_url,
        "confirmations_required": confirmations,
        "enabled": normalize_bool(data.get("enabled", True), True),
        "sort": int(data.get("sort", 100) or 100),
    }


def qr_payload(method, crypto_amount):
    asset = method.get("asset", "")
    address = method.get("address", "")
    amount = str(crypto_amount)
    if asset == "BTC":
        return f"bitcoin:{address}?amount={amount}"
    if asset in ("ETH", "BNB"):
        return f"ethereum:{address}?value={amount}"
    return address
```

- [ ] **Step 4: Use validation in store**

Modify `baseline/payments_store.py`:

```python
import payment_wallets
```

Replace the manual `method = {...}` body inside `upsert_method` with:

```python
    method = payment_wallets.normalize_method(data)
    method["updated_at"] = now_iso()
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/payment_wallets.py baseline/payments_store.py tests/test_crypto_payments.py
git commit -m "feat: validate crypto payment methods"
```

---

### Task 3: Rates And Decimal-Safe Amount Locking

**Files:**
- Create: `baseline/payment_rates.py`
- Test: `tests/test_crypto_payments.py`

- [ ] **Step 1: Add failing rate tests**

Append:

```python
def test_payment_rates_lock_amounts_with_overrides(payment_modules):
    payment_rates = importlib.import_module("payment_rates")
    payments_store = payment_modules["payments_store"]

    payments_store.save_rates({"overrides": {"ETH": "3000"}, "cache": {"BTC": {"rate_usd": "100000", "updated_at": "now"}}})

    assert payment_rates.rate_for_asset("USDT") == "1"
    assert payment_rates.rate_for_asset("ETH") == "3000"
    assert payment_rates.rate_for_asset("BTC") == "100000"
    assert payment_rates.crypto_amount_for_usd("39", "ETH", 18) == "0.013000000000000000"
    assert payment_rates.crypto_amount_for_usd("39", "BTC", 8) == "0.00039000"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_payment_rates_lock_amounts_with_overrides -q
```

Expected: FAIL because `payment_rates` does not exist.

- [ ] **Step 3: Implement rates**

Create `baseline/payment_rates.py`:

```python
from decimal import Decimal, ROUND_UP, getcontext

import payments_store


getcontext().prec = 42
STABLES = {"USDT", "USDC"}


def decimal_text(value):
    return str(value or "").strip()


def rate_for_asset(asset):
    asset = str(asset or "").strip().upper()
    if asset in STABLES:
        return "1"
    rates = payments_store.load_rates()
    override = decimal_text(rates.get("overrides", {}).get(asset, ""))
    if override:
        return str(Decimal(override))
    cached = rates.get("cache", {}).get(asset, {})
    cached_rate = decimal_text(cached.get("rate_usd", ""))
    if cached_rate:
        return str(Decimal(cached_rate))
    raise RuntimeError(f"missing USD rate for {asset}")


def crypto_amount_for_usd(usd_amount, asset, decimals):
    rate = Decimal(rate_for_asset(asset))
    if rate <= 0:
        raise RuntimeError("rate must be greater than 0")
    places = Decimal(1).scaleb(-int(decimals))
    amount = (Decimal(str(usd_amount)) / rate).quantize(places, rounding=ROUND_UP)
    return format(amount, f".{int(decimals)}f")


def save_overrides(overrides):
    rates = payments_store.load_rates()
    clean = {}
    for asset, value in (overrides or {}).items():
        asset = str(asset or "").strip().upper()
        value = str(value or "").strip()
        if not asset or not value:
            continue
        parsed = Decimal(value)
        if parsed <= 0:
            raise RuntimeError("override rate must be greater than 0")
        clean[asset] = str(parsed)
    rates["overrides"] = clean
    return payments_store.save_rates(rates)
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/payment_rates.py tests/test_crypto_payments.py
git commit -m "feat: add crypto payment rates"
```

---

### Task 4: Chain Verification Parsers

**Files:**
- Create: `baseline/payment_verifier.py`
- Test: `tests/test_crypto_payments.py`

- [ ] **Step 1: Add failing verifier parser tests**

Append:

```python
def pad_topic_address(addr):
    return "0x" + ("0" * 24) + addr.lower().replace("0x", "")


def test_evm_erc20_and_native_verification_parsers(payment_modules):
    verifier = importlib.import_module("payment_verifier")
    receiver = "0x2222222222222222222222222222222222222222"
    sender = "0x1111111111111111111111111111111111111111"
    contract = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    transfer_topic = verifier.ERC20_TRANSFER_TOPIC
    receipt = {
        "blockNumber": "0x64",
        "logs": [
            {
                "address": contract,
                "topics": [transfer_topic, pad_topic_address(sender), pad_topic_address(receiver)],
                "data": "0x" + format(39000000, "064x"),
            }
        ],
    }
    result = verifier.verify_evm_erc20_receipt(
        receipt,
        current_block=120,
        token_contract=contract,
        to_address=receiver,
        required_amount="39.000000",
        decimals=6,
        confirmations_required=12,
    )
    assert result["status"] == "confirmed"
    assert result["detected_amount"] == "39.000000"
    assert result["confirmations"] == 21

    tx = {"to": receiver, "value": "0x" + format(13000000000000000, "x"), "blockNumber": "0x64"}
    native = verifier.verify_evm_native_tx(
        tx,
        current_block=120,
        to_address=receiver,
        required_amount="0.013000000000000000",
        decimals=18,
        confirmations_required=12,
    )
    assert native["status"] == "confirmed"


def test_btc_verification_parser(payment_modules):
    verifier = importlib.import_module("payment_verifier")
    tx = {
        "status": {"confirmed": True, "block_height": 100},
        "vout": [
            {"scriptpubkey_address": "bc1qexample", "value": 39000},
            {"scriptpubkey_address": "bc1qother", "value": 1000},
        ],
    }
    result = verifier.verify_btc_tx(
        tx,
        tip_height=103,
        to_address="bc1qexample",
        required_amount="0.00039000",
        confirmations_required=3,
    )
    assert result["status"] == "confirmed"
    assert result["detected_amount"] == "0.00039000"
    assert result["confirmations"] == 4
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_evm_erc20_and_native_verification_parsers tests/test_crypto_payments.py::test_btc_verification_parser -q
```

Expected: FAIL because `payment_verifier` does not exist.

- [ ] **Step 3: Implement parser-only verifier functions**

Create `baseline/payment_verifier.py`:

```python
import json
import urllib.request
from decimal import Decimal


ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
WEI = Decimal("1000000000000000000")
SATOSHI = Decimal("100000000")


def normalize_address(addr):
    return str(addr or "").strip().lower()


def hex_int(value):
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value)
    return int(text, 16) if text.startswith("0x") else int(text)


def topic_to_address(topic):
    text = str(topic or "").lower().replace("0x", "")
    return "0x" + text[-40:]


def amount_from_units(raw, decimals):
    value = Decimal(int(raw)) / (Decimal(10) ** int(decimals))
    return format(value, f".{int(decimals)}f")


def status_for_amount_and_confirmations(amount, required, confirmations, confirmations_required):
    if Decimal(amount) < Decimal(required):
        return "failed"
    if int(confirmations) < int(confirmations_required):
        return "detected"
    return "confirmed"


def verify_evm_erc20_receipt(receipt, current_block, token_contract, to_address, required_amount, decimals, confirmations_required):
    token_contract = normalize_address(token_contract)
    to_address = normalize_address(to_address)
    block = hex_int(receipt.get("blockNumber"))
    confirmations = max(0, int(current_block) - block + 1) if block else 0
    total = Decimal(0)
    for log in receipt.get("logs", []):
        if normalize_address(log.get("address")) != token_contract:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3 or normalize_address(topics[0]) != normalize_address(ERC20_TRANSFER_TOPIC):
            continue
        if normalize_address(topic_to_address(topics[2])) != to_address:
            continue
        total += Decimal(hex_int(log.get("data", "0x0"))) / (Decimal(10) ** int(decimals))
    detected = format(total, f".{int(decimals)}f")
    status = status_for_amount_and_confirmations(detected, required_amount, confirmations, confirmations_required)
    return {"status": status, "detected_amount": detected, "confirmations": confirmations, "error": "" if total else "matching transfer not found"}


def verify_evm_native_tx(tx, current_block, to_address, required_amount, decimals, confirmations_required):
    if normalize_address(tx.get("to")) != normalize_address(to_address):
        return {"status": "failed", "detected_amount": format(Decimal(0), f".{int(decimals)}f"), "confirmations": 0, "error": "destination address mismatch"}
    block = hex_int(tx.get("blockNumber"))
    confirmations = max(0, int(current_block) - block + 1) if block else 0
    detected = format(Decimal(hex_int(tx.get("value", "0x0"))) / WEI, f".{int(decimals)}f")
    status = status_for_amount_and_confirmations(detected, required_amount, confirmations, confirmations_required)
    return {"status": status, "detected_amount": detected, "confirmations": confirmations, "error": ""}


def verify_btc_tx(tx, tip_height, to_address, required_amount, confirmations_required):
    total_sat = 0
    for out in tx.get("vout", []):
        if str(out.get("scriptpubkey_address") or "") == str(to_address):
            total_sat += int(out.get("value", 0) or 0)
    status = tx.get("status", {})
    block_height = int(status.get("block_height", 0) or 0)
    confirmations = max(0, int(tip_height) - block_height + 1) if status.get("confirmed") and block_height else 0
    detected = format(Decimal(total_sat) / SATOSHI, ".8f")
    payment_status = status_for_amount_and_confirmations(detected, required_amount, confirmations, confirmations_required)
    return {"status": payment_status, "detected_amount": detected, "confirmations": confirmations, "error": "" if total_sat else "matching output not found"}


def rpc_call(rpc_url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(rpc_url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(str(payload["error"].get("message") or "rpc error"))
    return payload.get("result")


def http_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/payment_verifier.py tests/test_crypto_payments.py
git commit -m "feat: add crypto payment verifiers"
```

---

### Task 5: Payment Service And Order Confirmation Integration

**Files:**
- Create: `baseline/payment_service.py`
- Modify: `tests/test_crypto_payments.py`

- [ ] **Step 1: Add failing service integration test**

Extend `MODULES` in `tests/test_crypto_payments.py`:

```python
    "auth_store",
    "user_store",
    "node_catalog",
    "plans_store",
    "orders_store",
    "audit_log",
    "admin_profile",
    "operations_service",
    "user_admin",
    "payment_rates",
    "payment_wallets",
    "payment_verifier",
    "payment_service",
```

Append:

```python
def test_confirmed_payment_completes_order(payment_modules, monkeypatch):
    plans_store = importlib.import_module("plans_store")
    orders_store = importlib.import_module("orders_store")
    payments_store = importlib.import_module("payments_store")
    payment_service = importlib.import_module("payment_service")
    user_admin = importlib.import_module("user_admin")

    monkeypatch.setattr(user_admin, "enforce_users_now", lambda: "ok")
    plan = plans_store.upsert_plan({"id": "standard", "name": "Standard", "days": "30", "traffic_gb": "100", "price": "39"})
    order = orders_store.create_pending_order("alice", "renew", plan, operator="alice")
    method = payments_store.upsert_method(
        {
            "id": "usdt-eth",
            "asset": "USDT",
            "chain": "ethereum",
            "address": "0x2222222222222222222222222222222222222222",
            "token_contract": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "decimals": "6",
            "rpc_url": "https://rpc.example",
            "confirmations_required": "12",
            "enabled": True,
        }
    )
    payment = payment_service.create_payment_for_order(order["id"], method["id"], "alice")
    assert payment["crypto_amount"] == "39.000000"

    monkeypatch.setattr(
        payment_service,
        "verify_payment",
        lambda p, m: {"status": "confirmed", "detected_amount": p["crypto_amount"], "confirmations": 12, "error": ""},
    )
    done = payment_service.submit_tx_and_verify(payment["id"], "0xtx", "alice")
    assert done["status"] == "confirmed"
    assert orders_store.get_order(order["id"])["status"] == "completed"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_confirmed_payment_completes_order -q
```

Expected: FAIL because `payment_service` does not exist.

- [ ] **Step 3: Implement service**

Create `baseline/payment_service.py`:

```python
from datetime import datetime, timedelta, timezone

import orders_store
import payment_rates
import payment_verifier
import payment_wallets
import payments_store
import user_admin


def now_utc():
    return datetime.now(timezone.utc)


def expires_at(hours=2):
    return (now_utc() + timedelta(hours=hours)).isoformat()


def require_payment_owner(payment, username, admin=False):
    if admin:
        return
    if payment.get("username") != username:
        raise RuntimeError("payment not found")


def create_payment_for_order(order_id, method_id, username, admin=False):
    order = orders_store.get_order(order_id)
    if not order:
        raise RuntimeError("order not found")
    if order.get("status") != "pending":
        raise RuntimeError("order is not pending")
    if not admin and order.get("username") != username:
        raise RuntimeError("order not found")
    method = payments_store.get_method(method_id)
    if not method or not method.get("enabled", True):
        raise RuntimeError("payment method not available")
    usd_amount = str(order.get("amount", 0))
    crypto_amount = payment_rates.crypto_amount_for_usd(usd_amount, method.get("asset"), method.get("decimals"))
    rate = payment_rates.rate_for_asset(method.get("asset"))
    payment = payments_store.create_payment(
        {
            "order_id": order_id,
            "username": order.get("username", username),
            "method_id": method_id,
            "asset": method.get("asset"),
            "chain": method.get("chain"),
            "usd_amount": usd_amount,
            "crypto_amount": crypto_amount,
            "rate_usd": rate,
            "address": method.get("address"),
            "qr_payload": payment_wallets.qr_payload(method, crypto_amount),
            "expires_at": expires_at(),
        }
    )
    orders_store.update_order(order_id, payment_id=payment["id"], payment_status=payment["status"])
    return payments_store.public_payment(payment, admin=True)


def verify_payment(payment, method):
    txid = payment.get("txid")
    if not txid:
        raise RuntimeError("txid is required")
    asset = payment.get("asset")
    chain = payment.get("chain")
    if chain in ("ethereum", "bsc"):
        current_block = payment_verifier.hex_int(payment_verifier.rpc_call(method.get("rpc_url"), "eth_blockNumber", []))
        if asset in ("USDT", "USDC"):
            receipt = payment_verifier.rpc_call(method.get("rpc_url"), "eth_getTransactionReceipt", [txid])
            if not receipt:
                return {"status": "detected", "detected_amount": "0", "confirmations": 0, "error": "transaction receipt not found"}
            return payment_verifier.verify_evm_erc20_receipt(
                receipt,
                current_block=current_block,
                token_contract=method.get("token_contract"),
                to_address=method.get("address"),
                required_amount=payment.get("crypto_amount"),
                decimals=method.get("decimals"),
                confirmations_required=method.get("confirmations_required"),
            )
        tx = payment_verifier.rpc_call(method.get("rpc_url"), "eth_getTransactionByHash", [txid])
        if not tx:
            return {"status": "detected", "detected_amount": "0", "confirmations": 0, "error": "transaction not found"}
        return payment_verifier.verify_evm_native_tx(
            tx,
            current_block=current_block,
            to_address=method.get("address"),
            required_amount=payment.get("crypto_amount"),
            decimals=method.get("decimals"),
            confirmations_required=method.get("confirmations_required"),
        )
    if chain == "bitcoin":
        base = method.get("btc_api_url", "").rstrip("/")
        tx = payment_verifier.http_json(f"{base}/tx/{txid}")
        tip = int(str(payment_verifier.http_json(f"{base}/blocks/tip/height")).strip())
        return payment_verifier.verify_btc_tx(
            tx,
            tip_height=tip,
            to_address=method.get("address"),
            required_amount=payment.get("crypto_amount"),
            confirmations_required=method.get("confirmations_required"),
        )
    raise RuntimeError("unsupported payment chain")


def apply_verification(payment_id, result, operator="system"):
    payment = payments_store.update_payment(
        payment_id,
        status=result.get("status", "failed"),
        detected_amount=result.get("detected_amount", ""),
        confirmations=int(result.get("confirmations", 0) or 0),
        error=str(result.get("error", ""))[:300],
    )
    orders_store.update_order(payment.get("order_id"), payment_status=payment.get("status"))
    if payment.get("status") == "confirmed":
        order = orders_store.get_order(payment.get("order_id"))
        if order and order.get("status") == "pending":
            user_admin.confirm_order(payment.get("order_id"), operator=operator)
    return payment


def refresh_payment(payment_id, username, admin=False):
    payment = payments_store.get_payment(payment_id)
    if not payment:
        raise RuntimeError("payment not found")
    require_payment_owner(payment, username, admin=admin)
    method = payments_store.get_method(payment.get("method_id"))
    if not method:
        raise RuntimeError("payment method not found")
    try:
        result = verify_payment(payment, method)
    except Exception as exc:
        result = {"status": payment.get("status", "awaiting_payment"), "detected_amount": payment.get("detected_amount", ""), "confirmations": payment.get("confirmations", 0), "error": str(exc)[:300]}
    return payments_store.public_payment(apply_verification(payment_id, result, operator=username), admin=admin)


def submit_tx_and_verify(payment_id, txid, username, admin=False):
    payment = payments_store.get_payment(payment_id)
    if not payment:
        raise RuntimeError("payment not found")
    require_payment_owner(payment, username, admin=admin)
    payment = payments_store.attach_txid(payment_id, txid)
    return refresh_payment(payment_id, username, admin=admin)
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/payment_service.py tests/test_crypto_payments.py
git commit -m "feat: connect crypto payments to orders"
```

---

### Task 6: Payment APIs And User POST Permission

**Files:**
- Create: `baseline/api_payment_routes.py`
- Modify: `baseline/api_get_routes.py`
- Modify: `baseline/api_post_routes.py`
- Modify: `tests/test_crypto_payments.py`
- Modify: `tests/test_core_api.py`

- [ ] **Step 1: Add failing API tests**

Append:

```python
def user_session(username):
    return {"u": username, "r": "user", "role": "user"}


def admin_session_for_payments():
    return {"u": "admin", "r": "admin", "role": "admin"}


def test_payment_api_user_flow(payment_modules, monkeypatch):
    api = importlib.import_module("api")
    plans_store = importlib.import_module("plans_store")
    payments_store = importlib.import_module("payments_store")
    payment_service = importlib.import_module("payment_service")
    user_admin = importlib.import_module("user_admin")

    monkeypatch.setattr(user_admin, "enforce_users_now", lambda: "ok")
    monkeypatch.setattr(
        payment_service,
        "verify_payment",
        lambda p, m: {"status": "confirmed", "detected_amount": p["crypto_amount"], "confirmations": 12, "error": ""},
    )
    plans_store.upsert_plan({"id": "standard", "name": "Standard", "days": "30", "traffic_gb": "100", "price": "39"})
    payments_store.upsert_method(
        {
            "id": "usdt-eth",
            "asset": "USDT",
            "chain": "ethereum",
            "address": "0x2222222222222222222222222222222222222222",
            "token_contract": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "rpc_url": "https://rpc.example",
            "confirmations_required": "12",
            "enabled": True,
        }
    )

    status, payload = api.handle_post("/api/orders/create", {"plan_id": "standard", "kind": "renew"}, user_session("alice"))
    assert status == 200
    order_id = payload["order"]["id"]

    status, payload = api.handle_post("/api/payments/create", {"order_id": order_id, "method_id": "usdt-eth"}, user_session("alice"))
    assert status == 200
    payment_id = payload["payment"]["id"]

    status, payload = api.handle_post("/api/payments/submit-tx", {"id": payment_id, "txid": "0xtx"}, user_session("alice"))
    assert status == 200
    assert payload["payment"]["status"] == "confirmed"


def test_payment_method_admin_api(payment_modules):
    api = importlib.import_module("api")
    status, payload = api.handle_post(
        "/api/payment-methods/save",
        {
            "id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "address": "bc1qexample",
            "btc_api_url": "https://blockstream.info/api",
            "confirmations_required": "3",
        },
        admin_session_for_payments(),
    )
    assert status == 200
    assert payload["method"]["id"] == "btc-main"

    status, payload = api.handle_get("/api/payment-methods", user_session("alice"))
    assert status == 200
    assert payload["methods"][0]["id"] == "btc-main"
    assert "btc_api_url" not in payload["methods"][0]
```

Update `MODULES` in both test files to include:

```python
    "payments_store",
    "payment_rates",
    "payment_wallets",
    "payment_verifier",
    "payment_service",
    "api_payment_routes",
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_payment_api_user_flow tests/test_crypto_payments.py::test_payment_method_admin_api -q
```

Expected: FAIL because API routes are not wired.

- [ ] **Step 3: Implement payment API routes**

Create `baseline/api_payment_routes.py`:

```python
import payment_rates
import payment_service
import payments_store
from api_common import ok, require_admin


def is_admin(session):
    return (session.get("role") or session.get("r")) == "admin"


def handle_payment_get(clean, session):
    admin = is_admin(session)
    username = "" if admin else session.get("u", "")
    if clean == "/api/payment-methods":
        return ok(methods=payments_store.list_methods(admin=admin), rates=payments_store.load_rates() if admin else {})
    if clean == "/api/payments":
        return ok(payments=payments_store.list_payments(username=None if admin else username, admin=admin, limit=200))
    return None


def handle_payment_post(clean, data, session):
    admin = is_admin(session)
    username = session.get("u", "")
    if clean == "/api/payment-methods/save":
        if (err := require_admin(session)):
            return err
        method = payments_store.upsert_method(data)
        return ok(method=payments_store.public_method(method, admin=True), methods=payments_store.list_methods(admin=True))
    if clean == "/api/payment-methods/action":
        if (err := require_admin(session)):
            return err
        action = data.get("action", "")
        method_id = data.get("id", "")
        if action == "enable":
            method = payments_store.set_method_enabled(method_id, True)
        elif action == "disable":
            method = payments_store.set_method_enabled(method_id, False)
        elif action == "delete":
            payments_store.delete_method(method_id)
            method = {"id": method_id}
        else:
            raise RuntimeError("unknown payment method action")
        return ok(method=method, methods=payments_store.list_methods(admin=True))
    if clean == "/api/payment-rates/save":
        if (err := require_admin(session)):
            return err
        overrides = data.get("overrides", data)
        rates = payment_rates.save_overrides(overrides)
        return ok(rates=rates)
    if clean == "/api/payments/create":
        payment = payment_service.create_payment_for_order(data.get("order_id", ""), data.get("method_id", ""), username, admin=admin)
        return ok(payment=payment, payments=payments_store.list_payments(username=None if admin else username, admin=admin))
    if clean == "/api/payments/submit-tx":
        payment = payment_service.submit_tx_and_verify(data.get("id", ""), data.get("txid", ""), username, admin=admin)
        return ok(payment=payment, payments=payments_store.list_payments(username=None if admin else username, admin=admin))
    if clean == "/api/payments/refresh":
        payment = payment_service.refresh_payment(data.get("id", ""), username, admin=admin)
        return ok(payment=payment, payments=payments_store.list_payments(username=None if admin else username, admin=admin))
    return None
```

- [ ] **Step 4: Wire GET routes**

Modify `baseline/api_get_routes.py`:

```python
from api_payment_routes import handle_payment_get
```

After authentication check and before the final return:

```python
    payment_result = handle_payment_get(clean, session)
    if payment_result is not None:
        return payment_result
```

- [ ] **Step 5: Wire user POST routes before admin gate**

Modify `baseline/api_post_routes.py`:

```python
from api_payment_routes import handle_payment_post
```

Replace the admin gate block with:

```python
    role = session.get("role") or session.get("r")
    if role != "admin":
        if clean == "/api/orders/create":
            result = handle_user_post(clean, data, session)
            if result is not None:
                return result
        payment_result = handle_payment_post(clean, data, session)
        if payment_result is not None:
            return payment_result
        return api_error("forbidden", 403)

    for handler in (handle_admin_post, handle_user_post, handle_node_post, handle_payment_post):
        result = handler(clean, data, session)
        if result is not None:
            return result
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py tests/test_core_api.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/api_payment_routes.py baseline/api_get_routes.py baseline/api_post_routes.py tests/test_crypto_payments.py tests/test_core_api.py
git commit -m "feat: expose crypto payment APIs"
```

---

### Task 7: Dashboard Payloads And Backups

**Files:**
- Modify: `baseline/dashboard_service.py`
- Modify: `baseline/backup_manager.py`
- Test: `tests/test_crypto_payments.py`

- [ ] **Step 1: Add failing payload/backup tests**

Append:

```python
def test_dashboard_includes_payment_data_and_backup_includes_payments(payment_modules):
    dashboard_service = importlib.import_module("dashboard_service")
    backup_manager = importlib.import_module("backup_manager")
    payments_store = importlib.import_module("payments_store")

    payments_store.upsert_method(
        {
            "id": "btc-main",
            "asset": "BTC",
            "chain": "bitcoin",
            "address": "bc1qexample",
            "btc_api_url": "https://blockstream.info/api",
            "confirmations_required": "3",
        }
    )
    user_payload = dashboard_service.dashboard({"u": "alice", "r": "user", "role": "user"})
    assert "payment_methods" in user_payload
    assert user_payload["payment_methods"][0]["id"] == "btc-main"
    assert "payments" in user_payload
    assert "payments.json" in backup_manager.BACKUP_FILES
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py::test_dashboard_includes_payment_data_and_backup_includes_payments -q
```

Expected: FAIL because dashboard does not include payment data and backups omit `payments.json`.

- [ ] **Step 3: Modify dashboard payloads**

In `baseline/dashboard_service.py`, import:

```python
import payments_store
```

In admin payload section, add:

```python
                "payment_methods": payments_store.list_methods(admin=True),
                "payments": payments_store.list_payments(admin=True, limit=80),
                "payment_rates": payments_store.load_rates(),
```

In user payload section, add:

```python
        payload["payment_methods"] = payments_store.list_methods(admin=False)
        payload["payments"] = payments_store.list_payments(username=username, admin=False, limit=30)
```

- [ ] **Step 4: Include payments in backups**

In `baseline/backup_manager.py`, add to `BACKUP_FILES`:

```python
    "payments.json",
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py tests/test_core_api.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/dashboard_service.py baseline/backup_manager.py tests/test_crypto_payments.py
git commit -m "feat: include crypto payments in dashboard backups"
```

---

### Task 8: Frontend Payment UI

**Files:**
- Modify: `baseline/frontend/assets/app.js`
- Modify: `baseline/frontend/assets/style.css`

- [ ] **Step 1: Add payment helpers in frontend**

In `baseline/frontend/assets/app.js`, add after `orderKindLabel`:

```javascript
function paymentStatusPill(status) {
  const cls = status === "confirmed" ? "on" : status === "detected" || status === "awaiting_payment" ? "warn" : "off";
  const label = { awaiting_payment: "待付款", detected: "已检测", confirmed: "已确认", failed: "失败", expired: "已过期" }[status] || status || "-";
  return `<span class="pill ${cls}">${esc(label)}</span>`;
}

function paymentForOrder(orderId) {
  return (state.data?.payments || []).find((p) => p.order_id === orderId) || null;
}

function paymentMethodOptions() {
  const methods = state.data?.payment_methods || [];
  return methods.map((m) => `<option value="${esc(m.id)}">${esc(m.label || `${m.asset} / ${m.chain}`)} - ${esc(m.asset)} ${esc(m.chain)}</option>`).join("");
}
```

- [ ] **Step 2: Update order table with payment controls**

Replace `orderTable` with a version that adds payment columns:

```javascript
function orderTable(orders, adminActions = false) {
  const payCol = `<th>支付</th>`;
  return `<div class="table-wrap"><table><thead><tr><th>时间</th><th>用户</th><th>类型</th><th>套餐</th><th>天数</th><th>流量</th><th>状态</th>${payCol}${adminActions ? "<th>操作</th>" : ""}</tr></thead><tbody>
    ${orders.map((o) => {
      const payment = paymentForOrder(o.id);
      const paymentCell = payment ? `<div class="payment-mini">${paymentStatusPill(payment.status)}<br><span class="muted">${esc(payment.asset || "")} ${esc(payment.chain || "")}</span><br><button type="button" class="secondary tiny" data-action="payment-refresh" data-payment="${esc(payment.id)}">刷新</button></div>` : (o.status === "pending" ? `<button type="button" class="good tiny" data-action="payment-start" data-order="${esc(o.id)}">付款</button>` : "-");
      const adminCell = adminActions ? `<td>${o.status === "pending" ? `<button type="button" class="secondary" data-action="order-action" data-order="${esc(o.id)}" data-order-action="confirm">确认</button><button type="button" class="danger" data-action="order-action" data-order="${esc(o.id)}" data-order-action="cancel">取消</button>` : ""}</td>` : "";
      return `<tr><td>${esc(o.created_at)}</td><td>${esc(o.username)}</td><td>${esc(orderKindLabel(o.kind))}</td><td>${esc(o.plan_name || o.plan_id)}</td><td>${esc(o.days)}</td><td>${esc(o.traffic_gb)} GB</td><td>${orderStatusPill(o.status)}</td><td>${paymentCell}</td>${adminCell}</tr>`;
    }).join("") || `<tr><td colspan="${adminActions ? 9 : 8}">暂无订单</td></tr>`}
  </tbody></table></div>`;
}
```

- [ ] **Step 3: Add payment panel to orders view**

In `ordersView`, before the order list section, add:

```javascript
  const methods = state.data?.payment_methods || [];
  const pendingOrders = orders.filter((o) => o.status === "pending");
  const paymentPanel = methods.length ? `<section class="panel">
    <h2>链上付款</h2>
    <form data-form="payment-create">
      <div class="form-grid"><div><label>订单</label><select name="order_id">${pendingOrders.map((o) => `<option value="${esc(o.id)}">${esc(o.plan_name || o.plan_id)} / $${esc(o.amount || 0)} / ${esc(o.id)}</option>`).join("")}</select></div><div><label>方式</label><select name="method_id">${paymentMethodOptions()}</select></div></div>
      <button class="good" ${pendingOrders.length ? "" : "disabled"}>生成付款二维码</button>
    </form>
  </section>` : `<section class="panel"><h2>链上付款</h2><p>暂无可用加密货币付款方式。</p></section>`;
```

Include `${paymentPanel}` before the order list.

- [ ] **Step 4: Render payment detail cards**

Add:

```javascript
function paymentsViewBlock() {
  const payments = state.data?.payments || [];
  if (!payments.length) return "";
  return `<section class="panel"><h2>付款记录</h2><div class="payment-grid">${payments.map((p) => `<div class="payment-card">
    <div class="section-head"><div><h2>${esc(p.asset)} / ${esc(p.chain)}</h2><p>${esc(p.order_id)}</p></div>${paymentStatusPill(p.status)}</div>
    <div class="kv-row"><span>应付金额</span><strong>${esc(p.crypto_amount)} ${esc(p.asset)}</strong></div>
    <div class="kv-row"><span>收款地址</span><code>${esc(p.address)}</code></div>
    <div class="copy-row"><input readonly value="${esc(p.qr_payload || p.address || "")}"><button type="button" class="secondary" data-copy="${esc(p.qr_payload || p.address || "")}">复制</button></div>
    <form data-form="payment-submit">
      <input type="hidden" name="id" value="${esc(p.id)}">
      <label>交易哈希 / txid</label><input name="txid" value="${esc(p.txid || "")}" placeholder="付款后填写 txid">
      <button class="good">提交并验证</button>
    </form>
    ${p.error ? `<p class="muted">${esc(p.error)}</p>` : ""}
  </div>`).join("")}</div></section>`;
}
```

Append `${paymentsViewBlock()}` in `ordersView` after the order table.

- [ ] **Step 5: Add admin payment config under settings**

In `settingsView`, add a payment methods section if admin:

```javascript
const paymentMethods = state.data?.payment_methods || [];
const paymentSettings = state.session?.role === "admin" ? `<section class="panel">
  <h2>加密货币收款</h2>
  <form data-form="payment-method-save">
    <div class="form-grid"><div><label>ID</label><input name="id" placeholder="usdt-eth"></div><div><label>排序</label><input name="sort" value="100"></div></div>
    <div class="form-grid"><div><label>资产</label><select name="asset"><option>USDT</option><option>USDC</option><option>ETH</option><option>BNB</option><option>BTC</option></select></div><div><label>链</label><select name="chain"><option value="ethereum">Ethereum</option><option value="bsc">BSC</option><option value="bitcoin">Bitcoin</option></select></div></div>
    <label>收款地址</label><input name="address" placeholder="0x... / bc1...">
    <label>Token 合约（USDT/USDC 必填）</label><input name="token_contract" placeholder="0x...">
    <label>EVM RPC URL</label><input name="rpc_url" placeholder="https://...">
    <label>BTC API URL</label><input name="btc_api_url" value="https://blockstream.info/api">
    <div class="form-grid"><div><label>确认数</label><input name="confirmations_required" value="12"></div><div><label>精度</label><input name="decimals" value="6"></div></div>
    <button class="good">保存收款方式</button>
  </form>
  <div class="table-wrap"><table><thead><tr><th>ID</th><th>资产</th><th>链</th><th>地址</th><th>状态</th><th>操作</th></tr></thead><tbody>${paymentMethods.map((m) => `<tr><td>${esc(m.id)}</td><td>${esc(m.asset)}</td><td>${esc(m.chain)}</td><td>${esc(m.address)}</td><td>${m.enabled ? "启用" : "停用"}</td><td><button type="button" class="secondary tiny" data-action="payment-method-action" data-method="${esc(m.id)}" data-method-action="${m.enabled ? "disable" : "enable"}">${m.enabled ? "停用" : "启用"}</button></td></tr>`).join("")}</tbody></table></div>
</section>` : "";
```

Insert `${paymentSettings}` in settings shell output.

- [ ] **Step 6: Wire frontend actions/forms**

In click handler, add:

```javascript
  else if (action === "payment-start") {
    const methods = state.data?.payment_methods || [];
    if (!methods.length) return showNotice("没有可用付款方式", "error");
    runAction(async () => {
      const out = await api("/api/payments/create", { method: "POST", body: { order_id: button.dataset.order || "", method_id: methods[0].id } });
      return `付款已生成：${out.payment.crypto_amount} ${out.payment.asset}`;
    });
  }
  else if (action === "payment-refresh") runAction(async () => { await api("/api/payments/refresh", { method: "POST", body: { id: button.dataset.payment || "" } }); return "支付状态已刷新"; });
  else if (action === "payment-method-action") runAction(async () => { await api("/api/payment-methods/action", { method: "POST", body: { id: button.dataset.method || "", action: button.dataset.methodAction || "" } }); return "收款方式已更新"; });
```

In submit handler, add:

```javascript
  else if (kind === "payment-create") runAction(async () => { const out = await api("/api/payments/create", { method: "POST", body: formData(form) }); return `付款已生成：${out.payment.crypto_amount} ${out.payment.asset}`; });
  else if (kind === "payment-submit") runAction(async () => { await api("/api/payments/submit-tx", { method: "POST", body: formData(form) }); return "交易已提交并验证"; });
  else if (kind === "payment-method-save") runAction(async () => { await api("/api/payment-methods/save", { method: "POST", body: formData(form) }); return "收款方式已保存"; });
```

- [ ] **Step 7: Add CSS**

Append to `baseline/frontend/assets/style.css`:

```css
.payment-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.payment-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: #fbfdff;
  display: grid;
  gap: 10px;
}
.payment-mini { display: grid; gap: 4px; align-items: start; }
code {
  overflow-wrap: anywhere;
  color: #132338;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}
@media (max-width: 860px) {
  .payment-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 8: Run tests and commit**

Run:

```powershell
python -m pytest tests/test_crypto_payments.py tests/test_core_api.py -q
```

Expected: PASS.

Commit:

```bash
git add baseline/frontend/assets/app.js baseline/frontend/assets/style.css
git commit -m "feat: add crypto payment UI"
```

---

### Task 9: Smoke, Docs, And Local Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/OPERATIONS.md`

- [ ] **Step 1: Update docs**

Add a short section to `README.md` feature table or operations area:

```markdown
| 加密货币支付 | USD 计价订单，管理员配置收款地址，支持 USDT/USDC/ETH/BNB/BTC 的收款二维码与链上验证 |
```

Add to `docs/OPERATIONS.md`:

```markdown
## 加密货币支付运维

- fake-ui 只保存收款地址和链上查询端点，不保存钱包私钥。
- 生产 RPC URL、API Key、真实收款地址应写入面板运行数据，不要提交到 Git。
- 新增或修改收款方式后，先用小额订单在测试机验证二维码、txid 提交、确认数和自动开通。
- 香港生产机上线前备份 `data/`，确认 `payments.json` 已包含在备份里。
```

- [ ] **Step 2: Run full local tests**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-local.ps1
```

Expected: pytest passes.

- [ ] **Step 3: Run git diff review**

Run:

```powershell
git diff --stat HEAD~9..HEAD
git status --short --branch
```

Expected: working tree clean after commits, changes limited to payment module, frontend UI, docs, and tests.

- [ ] **Step 4: Commit docs**

Commit:

```bash
git add README.md docs/OPERATIONS.md
git commit -m "docs: document crypto payment operations"
```

---

### Task 10: Singapore Deployment Verification Plan

**Files:**
- No code changes.

- [ ] **Step 1: Build release candidate locally**

Run:

```powershell
git status --short --branch
python -m pytest tests/test_crypto_payments.py tests/test_core_api.py -q
```

Expected: clean tree and all tests pass.

- [ ] **Step 2: Backup Singapore test deployment**

Run:

```powershell
ssh fake-ui-sg "cd /opt && tar czf /opt/fake-airport.pre-crypto-payments.$(date +%Y%m%d-%H%M%S).tgz fake-airport"
```

Expected: backup file path printed or command exits 0.

- [ ] **Step 3: Deploy to Singapore only**

Package current branch and deploy to `/opt/fake-airport` preserving `.env`, `data/`, and `generated/`. Rebuild panel image and restart panel. Do not touch Hong Kong production.

- [ ] **Step 4: Configure test payment methods**

In Singapore panel, configure test receive-only methods:

```text
USDT Ethereum: test receive address, public Ethereum RPC
USDC Ethereum: test receive address, public Ethereum RPC
USDT BSC: test receive address, public BSC RPC
USDC BSC: test receive address, public BSC RPC
ETH: test receive address, public Ethereum RPC
BNB: test receive address, public BSC RPC
BTC: test receive address, https://blockstream.info/api
```

Use only addresses intended for testing. Do not paste private keys.

- [ ] **Step 5: Verify end-to-end UI**

Checklist:

```text
Admin can save and enable payment methods.
User can create pending order.
User can generate payment intent.
Payment page shows exact crypto amount and QR payload.
Submitting a mocked or real low-value txid updates payment state.
Confirmed payment completes order and opens/renews account.
Manual order confirmation still works.
```

- [ ] **Step 6: Hong Kong production gate**

Do not deploy to Hong Kong until Singapore passes all checks and `data/` backup/rollback commands are verified.
