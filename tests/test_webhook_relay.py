"""Tests for the TradingView webhook relay's pure signal logic.

Imports only signal_logic (no fastapi/network), so runs on host Python.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webhook_relay"))

from signal_logic import classify, normalize_pair, parse_payload, valid_secret

SECRET = "test-secret-123"


def test_classify_entry_and_exit_synonyms():
    for a in ("buy", "long", "ENTER", "enter_long", "open"):
        assert classify(a) == "enter"
    for a in ("sell", "close", "EXIT", "flat"):
        assert classify(a) == "exit"
    assert classify("wibble") is None
    assert classify(None) is None


def test_valid_secret_constant_time():
    assert valid_secret(SECRET, SECRET) is True
    assert valid_secret("wrong", SECRET) is False
    assert valid_secret(SECRET, "") is False          # empty expected => reject
    assert valid_secret(None, SECRET) is False


def test_normalize_pair_forms():
    assert normalize_pair("BTC/USD") == "BTC/USD"
    assert normalize_pair("BTCUSD") == "BTC/USD"
    assert normalize_pair("KRAKEN:BTCUSD") == "BTC/USD"
    assert normalize_pair("ETH/USDT") == "ETH/USD"      # we trade USD spot
    assert normalize_pair("XBTUSD") == "BTC/USD"         # kraken legacy
    assert normalize_pair("sol/usd") == "SOL/USD"
    assert normalize_pair("") is None
    assert normalize_pair("garbage") is None


def test_parse_payload_happy_path():
    body = {"secret": SECRET, "action": "buy", "pair": "BTC/USD"}
    result, status = parse_payload(body, SECRET)
    assert status == 200 and result == {"kind": "enter", "pair": "BTC/USD"}


def test_parse_payload_rejects_bad_secret():
    body = {"secret": "nope", "action": "buy", "pair": "BTC/USD"}
    result, status = parse_payload(body, SECRET)
    assert status == 401 and "secret" in result["error"]


def test_parse_payload_rejects_unknown_action():
    body = {"secret": SECRET, "action": "hodl", "pair": "BTC/USD"}
    _, status = parse_payload(body, SECRET)
    assert status == 400


def test_parse_payload_rejects_bad_pair():
    body = {"secret": SECRET, "action": "buy", "pair": "???"}
    _, status = parse_payload(body, SECRET)
    assert status == 400


def test_parse_payload_accepts_ticker_field():
    body = {"secret": SECRET, "action": "sell", "ticker": "KRAKEN:XRPUSD"}
    result, status = parse_payload(body, SECRET)
    assert status == 200 and result == {"kind": "exit", "pair": "XRP/USD"}
