const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const msg = (t) => { document.getElementById("msg").textContent = t; };

let MODE = "local";

const paintMode = () => {
  const remote = MODE === "remote";
  document.getElementById("localOnly").hidden = remote;
  document.getElementById("remoteOnly").hidden = !remote;
  document.getElementById("modeLocal").className = remote ? "" : "primary";
  document.getElementById("modeRemote").className = remote ? "primary" : "";
};

const up = async () => {
  msg("starting…");
  try { await invoke("stack_up"); msg("stack started"); }
  catch (e) { msg("error: " + e); }
  refresh();
};

const down = async () => {
  msg("stopping…");
  try { await invoke("stack_down"); msg("stack stopped"); }
  catch (e) { msg("error: " + e); }
  refresh();
};

const dashboard = () => invoke("open_dashboard");
const frequi = () => invoke("open_frequi");

const setMode = async (mode) => {
  try {
    await invoke("set_connection_mode", { mode });
    MODE = mode;
    paintMode();
    document.getElementById("botUrl").innerHTML = "";
    await loadConnection();
    refresh();
  } catch (e) { msg("error: " + e); }
};

const loadConnection = async () => {
  const c = await invoke("get_connection");
  MODE = c.mode === "remote" ? "remote" : "local";
  paintMode();
  if (c.remote_origin) document.getElementById("remoteOrigin").value = c.remote_origin;
  const pill = document.getElementById("remotePill");
  if (c.remote_origin && c.remote_user_saved) {
    pill.textContent = "saved · " + (c.remote_user_hint || "user");
    pill.className = "pill ok";
    document.getElementById("remoteHint").textContent = "Talking to " + c.remote_origin + " over TLS.";
  } else {
    pill.textContent = "not set";
    pill.className = "pill bad";
    document.getElementById("remoteHint").textContent = "Save origin + WebUI login to load the remote fleet.";
  }
};

const saveRemote = async () => {
  try {
    const origin = await invoke("set_remote_origin", { origin: document.getElementById("remoteOrigin").value });
    document.getElementById("remoteOrigin").value = origin;
    const user = document.getElementById("remoteUser").value;
    const password = document.getElementById("remotePass").value;
    if (user && password) {
      await invoke("save_remote_webui", { user, password });
      document.getElementById("remotePass").value = "";
    }
    await invoke("set_connection_mode", { mode: "remote" });
    MODE = "remote";
    paintMode();
    document.getElementById("botUrl").innerHTML = "";
    msg("Remote console saved. Dry-run is never flipped.");
    await loadConnection();
    refresh();
  } catch (e) { msg("error: " + e); }
};

const clearRemote = async () => {
  try {
    await invoke("clear_remote_webui");
    msg("Remote WebUI login cleared");
    await loadConnection();
  } catch (e) { msg("error: " + e); }
};

const saveDir = async () => {
  try {
    await invoke("set_project_dir", { dir: document.getElementById("dir").value });
    msg("project folder saved");
    refresh();
  } catch (e) { msg("error: " + e); }
};

const browseDir = async () => {
  try {
    const dir = await invoke("pick_project_dir");
    if (dir) { document.getElementById("dir").value = dir; msg("project folder saved"); refresh(); }
  } catch (e) { msg("error: " + e); }
};

const probeRemote = async () => {
  msg("testing TLS…");
  try { msg(await invoke("probe_remote")); }
  catch (e) { msg("error: " + e); }
};

const toggleAutostart = async () => {
  const on = document.getElementById("autostart").checked;
  try { await invoke("set_autostart", { enabled: on }); msg(on ? "will start at login" : "autostart off"); }
  catch (e) { msg("error: " + e); }
};

const openKraken = () => invoke("open_kraken_api_page");

const refreshKeyState = async () => {
  try {
    const s = await invoke("kraken_key_status");
    const el = document.getElementById("keyState");
    el.textContent = s.saved ? ("saved · " + s.hint) : "not saved";
    el.className = "pill " + (s.saved ? "ok" : "bad");
  } catch (e) { msg("key status error: " + e); }
};

const saveKey = async () => {
  const key = document.getElementById("apiKey").value;
  const secret = document.getElementById("apiSecret").value;
  try {
    await invoke("save_kraken_key", { key, secret });
    document.getElementById("apiKey").value = "";
    document.getElementById("apiSecret").value = "";
    msg("Kraken key saved (encrypted in Windows Credential Manager)");
  } catch (e) { msg("error: " + e); }
  refreshKeyState();
};

const clearKey = async () => {
  try { await invoke("clear_kraken_key"); msg("Kraken key cleared"); }
  catch (e) { msg("error: " + e); }
  refreshKeyState();
};

const applyKey = async () => {
  try { msg(await invoke("apply_kraken_key_to_env")); }
  catch (e) { msg("error: " + e); }
};

const usd = (v) => v == null ? "—" : Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" });
const pct = (v) => v == null ? "—" : `${(Number(v) * 100).toFixed(2)}%`;
const signedPct = (v) => `${v >= 0 ? "+" : ""}${(Number(v) * 100).toFixed(2)}%`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));

const openDocker = () => invoke("open_docker_install");

const copyEnv = async () => {
  try { msg(await invoke("copy_env_example")); } catch (e) { msg("error: " + e); }
  refresh();
};

const refreshDocker = async () => {
  try {
    const h = await invoke("docker_health");
    const banner = document.getElementById("dockerBanner");
    const actions = document.getElementById("dockerActions");
    banner.hidden = false;
    banner.className = "banner " + (h.ready ? "ok" : "warn");
    banner.textContent = h.hint;
    actions.hidden = h.ready;
  } catch (e) { msg("docker check: " + e); }
};

const selectBot = (url) => {
  document.getElementById("botUrl").value = url;
  refreshSnapshot();
};

const renderFleet = (entries) => {
  const wrap = document.getElementById("fleet");
  const sel = document.getElementById("botUrl");
  if (!entries.length) { wrap.innerHTML = ""; return; }
  if (!sel.value) sel.value = entries[0].snapshot.url;
  wrap.onclick = (ev) => {
    const btn = ev.target.closest("[data-url]");
    if (btn) selectBot(btn.getAttribute("data-url"));
  };
  wrap.innerHTML = entries.map((e) => {
    const s = e.snapshot;
    const active = s.url === sel.value ? " active" : "";
    const mode = !s.reachable ? "offline" : (s.live_tripwire ? "LIVE" : "dry-run");
    const cls = !s.reachable || s.live_tripwire ? "bad" : "ok";
    const pnl = s.reachable ? usd(s.total_pnl) : "—";
    const pos = s.reachable ? `${s.open_positions.length} open` : (s.error || "offline");
    return `<button type="button" class="botcard${active}" data-url="${esc(s.url)}">
      <div class="top"><span>${esc(e.label)}</span><span class="${cls}">${esc(mode)} · ${esc(pnl)}</span></div>
      <div class="sub">${esc(pos)}</div>
    </button>`;
  }).join("");
};

const refreshSnapshot = async () => {
  const sel = document.getElementById("botUrl");
  const url = sel.value;
  const mode = document.getElementById("botMode");
  const trip = document.getElementById("tripwire");
  try {
    const s = await invoke("bot_snapshot", { url });
    trip.hidden = !s.live_tripwire;
    if (!s.reachable) {
      mode.textContent = "offline";
      mode.className = "pill bad";
      document.getElementById("kpiBal").textContent = "—";
      document.getElementById("kpiPnl").textContent = "—";
      document.getElementById("kpiTrades").textContent = "—";
      document.getElementById("kpiDd").textContent = "—";
      document.getElementById("botMeta").textContent = s.error || "bot unreachable";
      document.getElementById("positions").innerHTML = '<p class="hint">Bot not reachable.</p>';
      return;
    }
    mode.textContent = s.live_tripwire ? "LIVE" : "dry-run";
    mode.className = "pill " + (s.live_tripwire ? "bad" : "ok");
    document.getElementById("kpiBal").textContent = usd(s.balance);
    const pnlEl = document.getElementById("kpiPnl");
    pnlEl.textContent = usd(s.total_pnl);
    pnlEl.className = "val " + (s.total_pnl >= 0 ? "ok" : "bad");
    document.getElementById("kpiTrades").textContent =
      `${s.closed_trades} (${s.winning_trades}W/${s.losing_trades}L)`;
    document.getElementById("kpiDd").textContent = pct(s.max_drawdown);
    const parts = [s.strategy, s.state, s.stake_currency].filter(Boolean);
    document.getElementById("botMeta").textContent =
      `${parts.join(" · ")} · closed ${usd(s.closed_pnl)} · open ${usd(s.open_pnl)}`;
    const wrap = document.getElementById("positions");
    if (!s.open_positions.length) {
      wrap.innerHTML = '<p class="hint">None — waiting for a setup.</p>';
    } else {
      wrap.innerHTML = s.open_positions.map((p) =>
        `<div class="pos"><span>${esc(p.pair)}</span><span class="${p.profit_ratio >= 0 ? "ok" : "bad"}">${usd(p.profit_abs)} (${signedPct(p.profit_ratio)})</span></div>`
      ).join("");
    }
  } catch (e) {
    mode.textContent = "error";
    mode.className = "pill bad";
    document.getElementById("botMeta").textContent = String(e);
  }
};

const refresh = async () => {
  if (MODE !== "remote") {
    refreshDocker();
    try {
      const svcs = await invoke("stack_status");
      const el = document.getElementById("services");
      if (!svcs.length) {
        el.innerHTML = '<div class="svc"><span>no containers</span><span class="warn">stopped</span></div>';
      } else {
        el.innerHTML = svcs.map((s) => {
          const cls = /healthy|up/i.test(s.status) ? "ok" : "bad";
          return `<div class="svc"><span>${esc(s.name)}</span><span class="${cls}">${esc(s.status)}</span></div>`;
        }).join("");
      }
    } catch (e) { msg("status error: " + e); }
  }
  try {
    const fleet = await invoke("bot_fleet");
    const sel = document.getElementById("botUrl");
    if (!sel.options.length) {
      sel.innerHTML = fleet.map((e) => `<option value="${esc(e.snapshot.url)}">${esc(e.label)}</option>`).join("");
    }
    renderFleet(fleet);
  } catch (e) { msg("fleet error: " + e); }
  refreshSnapshot();
};

const bindUi = () => {
  document.getElementById("modeLocal").addEventListener("click", () => setMode("local"));
  document.getElementById("modeRemote").addEventListener("click", () => setMode("remote"));
  document.getElementById("btnUp").addEventListener("click", up);
  document.getElementById("btnDown").addEventListener("click", down);
  document.getElementById("btnRefreshLocal").addEventListener("click", refresh);
  document.getElementById("btnDashboardLocal").addEventListener("click", dashboard);
  document.getElementById("btnDockerInstall").addEventListener("click", openDocker);
  document.getElementById("btnCopyEnv").addEventListener("click", copyEnv);
  document.getElementById("autostart").addEventListener("change", toggleAutostart);
  document.getElementById("dir").addEventListener("change", saveDir);
  document.getElementById("btnBrowse").addEventListener("click", browseDir);
  document.getElementById("btnSaveRemote").addEventListener("click", saveRemote);
  document.getElementById("btnClearRemote").addEventListener("click", clearRemote);
  document.getElementById("btnProbeRemote").addEventListener("click", probeRemote);
  document.getElementById("btnDashboardRemote").addEventListener("click", dashboard);
  document.getElementById("btnFrequi").addEventListener("click", frequi);
  document.getElementById("btnRefreshRemote").addEventListener("click", refresh);
  document.getElementById("botUrl").addEventListener("change", refreshSnapshot);
  document.getElementById("btnOpenKraken").addEventListener("click", openKraken);
  document.getElementById("btnSaveKey").addEventListener("click", saveKey);
  document.getElementById("btnClearKey").addEventListener("click", clearKey);
  document.getElementById("btnApplyKey").addEventListener("click", applyKey);
};

const boot = async () => {
  bindUi();
  document.getElementById("dir").value = await invoke("get_project_dir");
  document.getElementById("autostart").checked = await invoke("autostart_enabled");
  await loadConnection();
  try {
    const bots = await invoke("bot_catalog");
    const sel = document.getElementById("botUrl");
    sel.innerHTML = bots.map((b) => `<option value="${esc(b.url)}">${esc(b.label)}</option>`).join("");
  } catch (e) { msg("catalog: " + e); }
  refreshKeyState();
  if (MODE !== "remote") refreshDocker();
  refresh();
  setInterval(refresh, 15000);
  setInterval(() => { if (MODE !== "remote") refreshDocker(); }, 30000);
};

listen("stack-changed", refresh);
boot();
