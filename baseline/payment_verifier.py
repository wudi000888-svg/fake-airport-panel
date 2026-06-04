import json
import urllib.request
from decimal import Decimal, InvalidOperation, getcontext


getcontext().prec = 78

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def normalize_address(value):
    text = str(value or "").strip().lower()
    if text.startswith("0x"):
        return text
    return "0x" + text


def hex_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text, 16 if text.lower().startswith("0x") else 10)
    except (TypeError, ValueError):
        return default


def topic_to_address(topic):
    text = normalize_address(topic)
    if len(text) < 42:
        return text
    return "0x" + text[-40:]


def amount_from_units(units, decimals):
    places = int(decimals)
    amount = Decimal(int(units)) / (Decimal(10) ** places)
    return f"{amount:.{places}f}"


def _decimal_amount(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return Decimal(0)
    if not amount.is_finite():
        return Decimal(0)
    return amount


def _confirmations(block_number, current_height):
    block = hex_int(block_number)
    tip = int(current_height or 0)
    if block <= 0 or tip < block:
        return 0
    return tip - block + 1


def status_for_amount_and_confirmations(amount, required_amount, confirmations, confirmations_required):
    detected = _decimal_amount(amount)
    required = _decimal_amount(required_amount)
    if detected < required:
        return "failed"
    if int(confirmations) < int(confirmations_required):
        return "detected"
    return "confirmed"


def _result(status, detected_amount, confirmations, error=""):
    return {
        "status": status,
        "detected_amount": detected_amount,
        "confirmations": confirmations,
        "error": error,
    }


def verify_evm_erc20_receipt(
    receipt,
    current_block,
    token_contract,
    to_address,
    required_amount,
    decimals,
    confirmations_required,
):
    places = int(decimals)
    zero_amount = amount_from_units(0, places)
    confirmations = _confirmations(dict(receipt or {}).get("blockNumber"), current_block)
    wanted_contract = normalize_address(token_contract)
    wanted_to = normalize_address(to_address)

    for log in dict(receipt or {}).get("logs", []) or []:
        topics = list(dict(log or {}).get("topics", []) or [])
        if normalize_address(dict(log or {}).get("address")) != wanted_contract:
            continue
        if len(topics) < 3 or str(topics[0]).lower() != ERC20_TRANSFER_TOPIC:
            continue
        if topic_to_address(topics[2]) != wanted_to:
            continue

        detected_amount = amount_from_units(hex_int(dict(log or {}).get("data")), places)
        status = status_for_amount_and_confirmations(
            detected_amount, required_amount, confirmations, confirmations_required
        )
        error = ""
        if status == "failed":
            error = "detected amount below required amount"
        elif status == "detected":
            error = "confirmations below required amount"
        return _result(status, detected_amount, confirmations, error)

    status = status_for_amount_and_confirmations(
        zero_amount, required_amount, confirmations, confirmations_required
    )
    return _result(status, zero_amount, confirmations, "matching ERC20 transfer not found")


def verify_evm_native_tx(tx, current_block, to_address, required_amount, decimals, confirmations_required):
    item = dict(tx or {})
    confirmations = _confirmations(item.get("blockNumber"), current_block)
    places = int(decimals)
    detected_amount = amount_from_units(hex_int(item.get("value")), places)

    if normalize_address(item.get("to")) != normalize_address(to_address):
        return _result("failed", amount_from_units(0, places), confirmations, "destination address mismatch")

    status = status_for_amount_and_confirmations(
        detected_amount, required_amount, confirmations, confirmations_required
    )
    error = ""
    if status == "failed":
        error = "detected amount below required amount"
    elif status == "detected":
        error = "confirmations below required amount"
    return _result(status, detected_amount, confirmations, error)


def verify_btc_tx(tx, tip_height, to_address, required_amount, confirmations_required):
    item = dict(tx or {})
    status = dict(item.get("status") or {})
    block_height = int(status.get("block_height") or 0)
    confirmations = 0
    if status.get("confirmed") and block_height > 0 and int(tip_height or 0) >= block_height:
        confirmations = int(tip_height) - block_height + 1

    total_sats = 0
    for output in item.get("vout", []) or []:
        output = dict(output or {})
        if str(output.get("scriptpubkey_address") or "") == str(to_address or ""):
            total_sats += int(output.get("value") or 0)

    detected_amount = amount_from_units(total_sats, 8)
    parsed_status = status_for_amount_and_confirmations(
        detected_amount, required_amount, confirmations, confirmations_required
    )
    error = ""
    if total_sats == 0:
        error = "matching Bitcoin output not found"
    elif parsed_status == "failed":
        error = "detected amount below required amount"
    elif parsed_status == "detected":
        error = "confirmations below required amount"
    return _result(parsed_status, detected_amount, confirmations, error)


def rpc_call(rpc_url, method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        str(rpc_url),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data.get("result")


def http_json(url):
    request = urllib.request.Request(str(url), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
