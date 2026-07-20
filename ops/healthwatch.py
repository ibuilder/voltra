"""Voltra health monitor + alerting sidecar.

Polls every bot's REST API and raises alerts on:
  - unreachable API or non-running state
  - DRY-RUN TRIPWIRE: any bot reporting dry_run=False. Going live is a
    human-only change; a bot in live mode that nobody authorized is a
    security incident, so this fires CRITICAL every cycle until resolved.

Alerts go to the log always, and additionally to ALERT_WEBHOOK_URL (generic
JSON POST) and/or Telegram if configured. Runs in the freqtrade image.

Env:
  HEALTHWATCH_TARGETS   comma list name=url (default the three bots)
  HEALTHWATCH_INTERVAL  seconds between polls (default 120)
  ALERT_WEBHOOK_URL     optional generic webhook for alerts
  FREQTRADE__TELEGRAM__TOKEN / __CHAT_ID   optional Telegram alerts
  FREQTRADE__API_SERVER__USERNAME / __PASSWORD   bot REST login
"""

import os
import time

import requests

USER = os.environ.get("FREQTRADE__API_SERVER__USERNAME", "")
PASS = os.environ.get("FREQTRADE__API_SERVER__PASSWORD", "")
INTERVAL = int(os.environ.get("HEALTHWATCH_INTERVAL", "60"))
STARTUP_GRACE = int(os.environ.get("HEALTHWATCH_GRACE", "90"))    # let the stack boot
FAIL_THRESHOLD = int(os.environ.get("HEALTHWATCH_FAILS", "2"))    # debounce flapping
ALERT_WEBHOOK = os.environ.get("ALERT_WEBHOOK_URL", "")
TG_TOKEN = os.environ.get("FREQTRADE__TELEGRAM__TOKEN", "")
TG_CHAT = os.environ.get("FREQTRADE__TELEGRAM__CHAT_ID", "")

DEFAULT_TARGETS = (
    "voltra-dry=http://freqtrade:8080,"
    "voltra-cross=http://freqtrade-cross:8080,"
    "voltra-webhook=http://freqtrade-webhook:8080"
)
TARGETS = [
    tuple(t.split("=", 1))
    for t in os.environ.get("HEALTHWATCH_TARGETS", DEFAULT_TARGETS).split(",")
    if "=" in t
]

_tokens: dict[str, str] = {}
_last_state: dict[str, str] = {}
_fail_streak: dict[str, int] = {}


def log(msg: str) -> None:
    print(f"[healthwatch] {msg}", flush=True)


def send_alert(level: str, name: str, msg: str) -> None:
    text = f"[Voltra {level}] {name}: {msg}"
    log(text)
    if ALERT_WEBHOOK:
        try:
            requests.post(ALERT_WEBHOOK, json={"level": level, "target": name, "message": msg}, timeout=10)
        except requests.RequestException as e:
            log(f"alert webhook failed: {type(e).__name__}")
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": text}, timeout=10)
        except requests.RequestException as e:
            log(f"telegram alert failed: {type(e).__name__}")


def token(name: str, url: str) -> str | None:
    if _tokens.get(name):
        return _tokens[name]
    try:
        r = requests.post(f"{url}/api/v1/token/login", auth=(USER, PASS), timeout=10)
        r.raise_for_status()
        _tokens[name] = r.json()["access_token"]
        return _tokens[name]
    except requests.RequestException:
        return None


def classify_config(cfg: dict) -> tuple[str, str]:
    """Pure decision from a bot's show_config. Returns (state, detail) with
    state in ok|warn|critical. The dry_run tripwire is the top priority."""
    if cfg.get("dry_run") is False:
        return "critical", "DRY-RUN TRIPWIRE: bot is LIVE (dry_run=false) — unauthorized?"
    if cfg.get("state") != "running":
        return "warn", f"state={cfg.get('state')}"
    return "ok", f"running, dry_run, {cfg.get('strategy')}"


def check(name: str, url: str) -> tuple[str, str]:
    """Return (state, detail). state in ok|warn|critical."""
    tok = token(name, url)
    if not tok:
        return "critical", "unreachable / login failed"
    try:
        r = requests.get(f"{url}/api/v1/show_config",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=10)
        if r.status_code == 401:
            _tokens.pop(name, None)
            return "warn", "auth expired (will retry)"
        r.raise_for_status()
        cfg = r.json()
    except requests.RequestException as e:
        return "critical", f"API error: {type(e).__name__}"
    return classify_config(cfg)


def main() -> None:
    log(f"start: {len(TARGETS)} targets, interval {INTERVAL}s, grace {STARTUP_GRACE}s, "
        f"debounce {FAIL_THRESHOLD}, "
        f"webhook={'yes' if ALERT_WEBHOOK else 'no'}, telegram={'yes' if TG_TOKEN and TG_CHAT else 'no'}")
    time.sleep(STARTUP_GRACE)  # let the stack finish booting before first poll
    while True:
        for name, url in TARGETS:
            state, detail = check(name, url)

            # The dry_run tripwire is a security event — alert immediately, no
            # debounce. Everything else must fail FAIL_THRESHOLD times in a row.
            is_tripwire = "TRIPWIRE" in detail
            if state == "critical":
                _fail_streak[name] = _fail_streak.get(name, 0) + 1
            else:
                _fail_streak[name] = 0

            confirmed_bad = is_tripwire or _fail_streak.get(name, 0) >= FAIL_THRESHOLD
            prev = _last_state.get(name)

            if state == "critical" and confirmed_bad and prev != "critical":
                send_alert("CRITICAL", name, detail)
                _last_state[name] = "critical"
            elif state == "ok" and prev == "critical":
                send_alert("RECOVERED", name, detail)
                _last_state[name] = "ok"
            elif prev is None and state == "ok":
                log(f"{name}: ok ({detail})")
                _last_state[name] = "ok"
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
