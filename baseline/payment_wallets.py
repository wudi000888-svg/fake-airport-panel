import re
from copy import deepcopy


STABLE_ASSETS = {"USDT", "USDC"}
SUPPORTED = {
    ("USDT", "ethereum"),
    ("USDC", "ethereum"),
    ("USDT", "bsc"),
    ("USDC", "bsc"),
    ("ETH", "ethereum"),
    ("BNB", "bsc"),
    ("BTC", "bitcoin"),
}
EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BTC_BECH32_RE = re.compile(r"^(bc1|tb1)[023456789acdefghjklmnpqrstuvwxyz]{20,}$", re.IGNORECASE)
BTC_BASE58_RE = re.compile(r"^[13mn2][123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{25,34}$")

PAYMENT_PRESETS = {
    ("USDT", "ethereum"): {
        "id": "usdt-eth",
        "decimals": 6,
        "confirmations_required": 12,
        "sort": 100,
        "token_contract": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"],
    },
    ("USDT", "bsc"): {
        "id": "usdt-bsc",
        "decimals": 18,
        "confirmations_required": 12,
        "sort": 110,
        "token_contract": "0x55d398326f99059ff775485246999027b3197955",
        "rpc_urls": [
            "https://bsc-rpc.publicnode.com",
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.binance.org",
        ],
    },
    ("ETH", "ethereum"): {
        "id": "eth-main",
        "decimals": 18,
        "confirmations_required": 12,
        "sort": 120,
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"],
    },
    ("USDC", "ethereum"): {
        "id": "usdc-eth",
        "decimals": 6,
        "confirmations_required": 12,
        "sort": 130,
        "token_contract": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"],
    },
    ("USDC", "bsc"): {
        "id": "usdc-bsc",
        "decimals": 18,
        "confirmations_required": 12,
        "sort": 140,
        "token_contract": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
        "rpc_urls": [
            "https://bsc-rpc.publicnode.com",
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.binance.org",
        ],
    },
    ("BNB", "bsc"): {
        "id": "bnb-main",
        "decimals": 18,
        "confirmations_required": 12,
        "sort": 150,
        "rpc_urls": [
            "https://bsc-rpc.publicnode.com",
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.binance.org",
        ],
    },
    ("BTC", "bitcoin"): {
        "id": "btc-main",
        "decimals": 8,
        "confirmations_required": 3,
        "sort": 160,
        "btc_api_urls": ["https://blockstream.info/api", "https://mempool.space/api"],
    },
}


def is_evm_chain(chain):
    return chain in ("ethereum", "bsc")


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled", ""}:
        return False
    raise RuntimeError("invalid boolean value")


def clean_id(value):
    method_id = str(value or "").strip()
    if not method_id:
        raise RuntimeError("payment method id required")
    return method_id


def preset_for(asset, chain):
    return deepcopy(PAYMENT_PRESETS.get((asset, chain), {}))


def _split_urls(value):
    if value in ("", None):
        return []
    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = re.split(r"[\s,]+", str(value))
    urls = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in urls:
            urls.append(text)
    return urls


def _with_fallback_urls(item, primary_key, list_key, defaults):
    urls = []
    urls.extend(_split_urls(item.get(list_key)))
    urls.extend(_split_urls(item.get(primary_key)))
    urls.extend(_split_urls(defaults))
    deduped = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    if not deduped:
        raise RuntimeError(f"{primary_key} required")
    item[list_key] = deduped
    item[primary_key] = deduped[0]


def _int_value(value, field):
    try:
        text = str(value).strip()
        return int(text)
    except (TypeError, ValueError):
        raise RuntimeError(f"{field} must be an integer") from None


def validate_evm_address(value, field="EVM address"):
    address = str(value or "").strip()
    if not EVM_ADDRESS_RE.match(address):
        raise RuntimeError(f"{field} invalid")
    return address.lower()


def validate_btc_address(value):
    address = str(value or "").strip()
    if not (BTC_BECH32_RE.match(address) or BTC_BASE58_RE.match(address)):
        raise RuntimeError("Bitcoin address invalid")
    return address


def _positive_int(value, field):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise RuntimeError(f"{field} must be > 0")
    if number <= 0:
        raise RuntimeError(f"{field} must be > 0")
    return number


def _default_decimals(asset):
    if asset == "BTC":
        return 8
    if asset in {"ETH", "BNB"}:
        return 18
    return 6


def normalize_method(method):
    item = deepcopy(dict(method or {}))
    item["asset"] = str(item.get("asset") or "").strip().upper()
    item["chain"] = str(item.get("chain") or "").strip().lower()

    if (item["asset"], item["chain"]) not in SUPPORTED:
        raise RuntimeError("unsupported payment asset or chain")

    preset = preset_for(item["asset"], item["chain"])
    item["id"] = clean_id(item.get("id") or preset.get("id"))
    address = str(item.get("address") or "").strip()
    if not address:
        raise RuntimeError("payment address required")

    if is_evm_chain(item["chain"]):
        item["address"] = validate_evm_address(address)
        _with_fallback_urls(item, "rpc_url", "rpc_urls", preset.get("rpc_urls", []))
    elif item["chain"] == "bitcoin":
        item["address"] = validate_btc_address(address)
        _with_fallback_urls(item, "btc_api_url", "btc_api_urls", preset.get("btc_api_urls", []))

    if item["asset"] in STABLE_ASSETS:
        token_contract = item.get("token_contract") or preset.get("token_contract")
        if not str(token_contract or "").strip():
            raise RuntimeError("token contract required")
        item["token_contract"] = validate_evm_address(token_contract, field="token contract")

    if str(item.get("confirmations_required") or "").strip():
        item["confirmations_required"] = _positive_int(
            item["confirmations_required"], "confirmations_required"
        )
    else:
        item["confirmations_required"] = int(preset.get("confirmations_required") or 1)

    if str(item.get("decimals") or "").strip():
        item["decimals"] = _positive_int(item["decimals"], "decimals")
    else:
        item["decimals"] = int(preset.get("decimals") or _default_decimals(item["asset"]))

    if str(item.get("sort") or "").strip():
        item["sort"] = _int_value(item["sort"], "sort")
    else:
        item["sort"] = int(preset.get("sort") or 100)

    if "enabled" in item:
        item["enabled"] = normalize_bool(item["enabled"])
    else:
        item["enabled"] = True

    return item


def qr_payload(method, amount):
    asset = str(method.get("asset") or "").strip().upper()
    chain = str(method.get("chain") or "").strip().lower()
    address = str(method.get("address") or "").strip()
    value = str(amount)
    if asset == "BTC" and chain == "bitcoin":
        return f"bitcoin:{address}?amount={value}"
    if asset == "ETH" and chain == "ethereum":
        return f"ethereum:{address}?value={value}"
    if asset == "BNB" and chain == "bsc":
        return address
    if asset in STABLE_ASSETS:
        return address
    raise RuntimeError("unsupported payment asset or chain")
