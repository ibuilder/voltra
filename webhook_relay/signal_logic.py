"""Pure signal-mapping logic for the TradingView webhook relay.

No FastAPI/network imports here so tests run on plain host Python. relay.py
wires these into the HTTP layer.
"""

import hmac

ENTER_ACTIONS = {"buy", "long", "enter", "enter_long", "open"}
EXIT_ACTIONS = {"sell", "close", "exit", "exit_long", "flat"}


def classify(action) -> str | None:
    """Map a TradingView alert 'action' to 'enter' | 'exit' | None."""
    a = str(action or "").strip().lower()
    if a in ENTER_ACTIONS:
        return "enter"
    if a in EXIT_ACTIONS:
        return "exit"
    return None


def valid_secret(provided, expected) -> bool:
    """Constant-time shared-secret check. Empty expected => always reject."""
    if not expected:
        return False
    return hmac.compare_digest(str(provided), str(expected))


def normalize_pair(raw) -> str | None:
    """Accept 'BTC/USD', 'BTCUSD', 'KRAKEN:BTCUSD', 'BTC/USDT' -> 'BTC/USD'.

    We trade USD spot, so anything ending USD/USDT/USDC maps to <BASE>/USD.
    Returns None if it can't be parsed.
    """
    if not raw:
        return None
    s = str(raw).strip().upper()
    if ":" in s:            # strip exchange prefix e.g. KRAKEN:BTCUSD
        s = s.split(":", 1)[1]
    if "/" in s:
        base, _, quote = s.partition("/")
    else:
        for q in ("USDT", "USDC", "USD"):
            if s.endswith(q):
                base, quote = s[: -len(q)], q
                break
        else:
            return None
    base = base.replace("XBT", "BTC")
    if not base:
        return None
    return f"{base}/USD"


def parse_payload(body: dict, expected_secret: str):
    """Validate + normalize a TradingView webhook body.

    Returns (result_dict, http_status). result_dict has 'error' on failure or
    {'kind','pair'} on success.
    """
    if not isinstance(body, dict):
        return {"error": "body must be a JSON object"}, 400
    if not valid_secret(body.get("secret"), expected_secret):
        return {"error": "invalid secret"}, 401
    kind = classify(body.get("action"))
    pair = normalize_pair(body.get("pair") or body.get("ticker"))
    if kind is None:
        return {"error": f"unknown action: {body.get('action')!r}"}, 400
    if pair is None:
        return {"error": "missing/unparseable pair"}, 400
    return {"kind": kind, "pair": pair}, 200
