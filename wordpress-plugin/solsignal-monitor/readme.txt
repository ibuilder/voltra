=== SolSignal Monitor ===
Contributors: solsignal
Tags: freqtrade, trading, monitoring, dashboard
Requires at least: 6.0
Tested up to: 6.6
Requires PHP: 7.4
Stable tag: 0.1.0
License: MIT

Monitoring + control panel for SolSignal Freqtrade bots, via the Freqtrade REST API and WP-Cron.

== Description ==

SolSignal Monitor is a WordPress admin dashboard for the SolSignal Freqtrade
trading bots. It talks to each bot's REST API (server-side) and shows mode,
state, strategy, balance, open trades, and closed PnL. WP-Cron polls the bots
every 15 minutes, caches a snapshot, and emails a **dry-run tripwire** alert if
any bot ever reports `dry_run=false`.

**This plugin does NOT run the trading bot.** The bot is Freqtrade — a 24/7
Python service (Docker). WordPress and WP-Cron cannot host a persistent trade
loop; this is a monitor/control panel only, and it never enables live trading.

= Features =
* Settings for multiple bots (name|url), API username/password, alert email.
* Server-side REST calls (credentials never reach the browser).
* Admin dashboard with 30s live refresh (via admin-ajax).
* WP-Cron poller + dry-run tripwire email + unreachable alerts.
* Optional read-only `[solsignal_status]` shortcode (renders the cron snapshot).
* Optional, off-by-default start/stop controls (capability + nonce gated).

== Security ==

* All actions require the `manage_options` capability and a nonce.
* Prefer defining `SOLSIGNAL_API_PASSWORD` in wp-config.php over storing the
  password in the database.
* Only expose the bot REST API to WordPress over a trusted network or via the
  Caddy TLS ingress — never plain HTTP over the internet.
* WordPress is a large attack surface; keep it patched. Controls are off by
  default for this reason.

== WP-Cron reliability ==

WP-Cron fires on page loads. On a low-traffic site, add a real system cron and
disable the page-load trigger:

  // wp-config.php
  define('DISABLE_WP_CRON', true);

  # crontab
  */15 * * * * curl -s "https://your-site/wp-cron.php?doing_wp_cron" >/dev/null

== Installation ==

1. Copy the `solsignal-monitor` folder to `wp-content/plugins/`.
2. Activate it in Plugins.
3. SolSignal menu → Settings: set the bot URLs, username, password, alert email.
4. (Recommended) define SOLSIGNAL_API_PASSWORD in wp-config.php.

== Changelog ==

= 0.1.0 =
* Initial release: settings, REST client, dashboard, WP-Cron tripwire, shortcode.
