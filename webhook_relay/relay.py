"""TradingView -> Freqtrade webhook relay.

Receives a TradingView alert webhook (JSON), validates a shared secret, and
forwards it to a freqtrade bot's REST API as a forced entry/exit. Runs inside
the freqtrade image (which already ships fastapi + uvicorn + requests).

SECURITY: this endpoint places (simulated) trades. It authenticates callers
 ONLY by the shared secret in the payload, so it MUST be exposed to the
internet only behind HTTPS (reverse proxy / Cloudflare Tunnel / ngrok).
Never expose plain http. The container binds 127.0.0.1 by default.

Env:
  RELAY_SECRET                     shared secret TradingView must send
  RELAY_FREQTRADE_URL              e.g. http://freqtrade-webhook:8080
  FREQTRADE__API_SERVER__USERNAME  bot REST login (from .env)
  FREQTRADE__API_SERVER__PASSWORD
"""

import os

import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from signal_logic import parse_payload

SECRET = os.environ.get("RELAY_SECRET", "")
FT_URL = os.environ.get("RELAY_FREQTRADE_URL", "http://freqtrade-webhook:8080").rstrip("/")
FT_USER = os.environ.get("FREQTRADE__API_SERVER__USERNAME", "")
FT_PASS = os.environ.get("FREQTRADE__API_SERVER__PASSWORD", "")

app = FastAPI(title="SolSignal TradingView relay")
_token = {"v": None}


def _login() -> str:
    r = requests.post(f"{FT_URL}/api/v1/token/login", auth=(FT_USER, FT_PASS), timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def _api(method: str, path: str, **kw) -> requests.Response:
    """Call the bot REST API, refreshing the JWT once on 401."""
    for attempt in (1, 2):
        if not _token["v"]:
            _token["v"] = _login()
        r = requests.request(
            method, f"{FT_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {_token['v']}"}, timeout=15, **kw
        )
        if r.status_code == 401 and attempt == 1:
            _token["v"] = None
            continue
        return r
    return r


@app.get("/health")
def health():
    return {"status": "ok", "target": FT_URL, "secret_set": bool(SECRET)}


@app.post("/webhook")
async def webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "body is not valid JSON"}, status_code=400)

    result, status = parse_payload(body, SECRET)
    if status != 200:
        return JSONResponse(result, status_code=status)

    kind, pair = result["kind"], result["pair"]
    try:
        if kind == "enter":
            r = _api("POST", "/forceenter", json={"pair": pair, "side": "long"})
            return JSONResponse(
                {"status": "entry forwarded", "pair": pair, "bot_code": r.status_code},
                status_code=200 if r.ok else 502,
            )
        # exit: find open trade(s) for this pair, force-exit each
        status_resp = _api("GET", "/status")
        open_trades = status_resp.json() if status_resp.ok else []
        ids = [t["trade_id"] for t in open_trades if t.get("pair") == pair]
        if not ids:
            return JSONResponse({"status": "no open trade", "pair": pair}, status_code=200)
        for tid in ids:
            _api("POST", "/forceexit", json={"tradeid": tid})
        return JSONResponse({"status": "exit forwarded", "pair": pair, "trades": ids})
    except requests.RequestException as e:
        return JSONResponse({"error": f"bot unreachable: {type(e).__name__}"}, status_code=502)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="info")
