/** Browser-only Tauri stand-in for `index.html?preview=1`. Never loaded by the real app. */

const bots = [
  { url: "http://127.0.0.1:8084", slug: "xsmom", label: "Momentum — top-3 of 16", strategy: "CrossSectionalMomentumStrategy" },
  { url: "http://127.0.0.1:8083", slug: "dca", label: "Conservative — DCA", strategy: "DcaAccumulateStrategy" },
  { url: "http://127.0.0.1:8080", slug: "dry", label: "Aggressive — TrendBreak", strategy: "TrendBreakStrategy" },
  { url: "http://127.0.0.1:8081", slug: "cross", label: "Lead-lag — SolCross", strategy: "SolCrossSignalStrategy" },
  { url: "http://127.0.0.1:8082", slug: "webhook", label: "Experimental — webhook", strategy: "WebhookRelayStrategy" },
];

const state = {
  mode: "local",
  dir: "/workspace",
  autostart: false,
  origin: "",
  remoteUser: "",
  remotePass: "",
  krakenKey: "",
  stack: "up",
};

const snap = (bot, extra = {}) => ({
  url: bot.url,
  reachable: true,
  error: null,
  dry_run: true,
  live_tripwire: false,
  state: "running",
  strategy: bot.strategy,
  stake_currency: "USD",
  balance: 10040,
  closed_pnl: 4,
  open_pnl: 1.25,
  total_pnl: 5.25,
  closed_trades: 2,
  winning_trades: 2,
  losing_trades: 0,
  max_drawdown: 0.012,
  open_positions: [
    { pair: "BTC/USD", profit_abs: 1.25, profit_ratio: 0.01, open_rate: 60000, amount: 0.01 },
  ],
  ...extra,
});

const remoteUrl = (slug) =>
  state.origin ? `${state.origin}/bot/${slug}` : `https://trade.example.com/bot/${slug}`;

const catalog = () => {
  if (state.mode !== "remote") return bots;
  if (!state.origin) return [];
  return bots.map((b) => ({ ...b, url: remoteUrl(b.slug) }));
};

const fleet = () =>
  catalog().map((b) => {
    const extra = b.slug === "webhook" ? { reachable: false, error: "offline in preview", open_positions: [] } : {};
    return { label: b.label, snapshot: snap({ ...b, url: b.url }, extra) };
  });

const handlers = {
  get_project_dir: () => state.dir,
  set_project_dir: ({ dir }) => {
    if (!dir) throw "project folder is empty";
    state.dir = dir;
  },
  pick_project_dir: () => state.dir,
  autostart_enabled: () => state.autostart,
  set_autostart: ({ enabled }) => { state.autostart = !!enabled; },
  get_connection: () => ({
    mode: state.mode,
    remote_origin: state.origin,
    remote_user_saved: !!(state.remoteUser && state.remotePass),
    remote_user_hint: state.remoteUser ? `${state.remoteUser.slice(0, 3)}…` : "",
  }),
  set_connection_mode: ({ mode }) => {
    if (mode !== "local" && mode !== "remote") throw "mode must be local or remote";
    state.mode = mode;
  },
  set_remote_origin: ({ origin }) => {
    const raw = String(origin || "").trim().replace(/\/$/, "");
    if (!raw.startsWith("https://") || raw.includes(" ")) throw "remote origin must be https://";
    if (raw.includes("127.0.0.1") || raw.includes("localhost")) throw "remote origin must be a public hostname";
    state.origin = raw.toLowerCase();
    return state.origin;
  },
  save_remote_webui: ({ user, password }) => {
    if (!user || !password) throw "Remote WebUI username and password are required.";
    if (/\n|\r/.test(user) || /\n|\r/.test(password)) throw "WebUI password contains control characters";
    state.remoteUser = user.trim();
    state.remotePass = password.trim();
  },
  clear_remote_webui: () => { state.remoteUser = ""; state.remotePass = ""; },
  probe_remote: () => {
    if (state.mode !== "remote") throw "Switch to Remote VPS mode first.";
    if (!state.origin) throw "Set a remote origin like https://trade.example.com first.";
    if (!state.remoteUser || !state.remotePass) throw "Save the remote WebUI username and password first.";
    return `TLS + JWT ok at ${state.origin}/bot/dry (TrendBreakStrategy). Read-only; dry-run stays a human-only change.`;
  },
  bot_catalog: () => catalog(),
  bot_fleet: () => fleet(),
  bot_snapshot: ({ url }) => {
    const list = catalog();
    const bot = list.find((b) => b.url === url) || list[0];
    if (!bot) throw "no bot";
    if (bot.slug === "webhook") {
      return snap(bot, { reachable: false, error: "offline in preview", open_positions: [] });
    }
    return snap(bot);
  },
  docker_health: () => ({
    cli_found: true,
    daemon_ok: true,
    compose_file: true,
    env_exists: true,
    webui_password: true,
    ready: true,
    hint: "Docker ready. Snapshot stays read-only; dry-run is never flipped.",
  }),
  stack_status: () =>
    state.stack === "up"
      ? [
          { name: "voltra-freqtrade", status: "Up (healthy)" },
          { name: "voltra-freqtrade-dca", status: "Up (healthy)" },
          { name: "voltra-freqtrade-xsmom", status: "Up (healthy)" },
        ]
      : [],
  stack_up: () => { state.stack = "up"; return "started"; },
  stack_down: () => { state.stack = "down"; return "stopped"; },
  copy_env_example: () => ".env already exists — not overwritten.",
  open_dashboard: () => {},
  open_frequi: () => {},
  open_docker_install: () => {},
  open_kraken_api_page: () => {},
  kraken_key_status: () =>
    state.krakenKey
      ? { saved: true, hint: `${state.krakenKey.slice(0, 4)}…${state.krakenKey.slice(-4)}` }
      : { saved: false, hint: "" },
  save_kraken_key: ({ key, secret }) => {
    if (!key || !secret) throw "Both the API key and secret are required.";
    if (/\n|\r/.test(key) || /\n|\r/.test(secret)) throw "Kraken API key contains control characters";
    state.krakenKey = key.trim();
  },
  clear_kraken_key: () => { state.krakenKey = ""; },
  apply_kraken_key_to_env: () => {
    if (!state.krakenKey) throw "No Kraken key saved yet — save one first.";
    return "Key written to .env. Restart the stack to load it. Dry-run stays ON — going live is a separate, manual step.";
  },
};

window.__TAURI__ = {
  core: {
    invoke: async (cmd, args = {}) => {
      if (!(cmd in handlers)) throw `unknown command ${cmd}`;
      return handlers[cmd](args);
    },
  },
  event: {
    listen: async () => () => {},
  },
};
