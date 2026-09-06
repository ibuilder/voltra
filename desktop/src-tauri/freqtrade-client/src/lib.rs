//! Freqtrade REST client for the desktop controller.
//!
//! JWT-auths against a *localhost* bot and returns a read-only snapshot
//! (config, P&L, open positions). Tokens stay in this process — they are
//! never sent to the webview.
//!
//! SAFETY: this module is GET-only plus `/token/login`. It never writes
//! config, never calls start/stop/forceenter, and never flips `dry_run`.

use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::net::IpAddr;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;

const LOGIN_PATH: &str = "/api/v1/token/login";
const REQUEST_TIMEOUT: Duration = Duration::from_secs(8);
const TOKEN_TTL: Duration = Duration::from_secs(10 * 60);
const MAX_JSON_BODY: u64 = 256 * 1024;
const GET_PATHS: &[&str] = &["/show_config", "/profit", "/balance", "/status"];
const BLOCKED_HOST_SUFFIXES: &[&str] = &[
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".private",
    ".invalid",
    ".test",
];

/// Hard allowlist — local Docker-mapped APIs.
const ALLOWED_PORTS: &[u16] = &[8080, 8081, 8082, 8083, 8084];

/// Caddy `handle_path /bot/<slug>/*` names on a VPS. Nothing else is reachable.
const REMOTE_SLUGS: &[&str] = &["xsmom", "dca", "dry", "cross", "webhook"];

#[derive(Clone, Copy)]
struct BotDef {
    slug: &'static str,
    label: &'static str,
    strategy: &'static str,
    local_port: u16,
}

const BOT_DEFS: &[BotDef] = &[
    BotDef {
        slug: "xsmom",
        label: "Momentum — top-3 of 16",
        strategy: "CrossSectionalMomentumStrategy",
        local_port: 8084,
    },
    BotDef {
        slug: "dca",
        label: "Conservative — DCA",
        strategy: "DcaAccumulateStrategy",
        local_port: 8083,
    },
    BotDef {
        slug: "dry",
        label: "Aggressive — TrendBreak",
        strategy: "TrendBreakStrategy",
        local_port: 8080,
    },
    BotDef {
        slug: "cross",
        label: "Lead-lag — SolCross",
        strategy: "SolCrossSignalStrategy",
        local_port: 8081,
    },
    BotDef {
        slug: "webhook",
        label: "Experimental — webhook",
        strategy: "WebhookRelayStrategy",
        local_port: 8082,
    },
];

#[derive(Clone, Serialize)]
pub struct BotInfo {
    pub url: String,
    pub slug: String,
    pub label: String,
    pub strategy: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct OpenPosition {
    pub pair: String,
    pub profit_abs: f64,
    pub profit_ratio: f64,
    pub open_rate: Option<f64>,
    pub amount: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct BotSnapshot {
    pub url: String,
    pub reachable: bool,
    pub error: Option<String>,
    pub dry_run: Option<bool>,
    pub live_tripwire: bool,
    pub state: Option<String>,
    pub strategy: Option<String>,
    pub stake_currency: Option<String>,
    pub balance: Option<f64>,
    pub closed_pnl: f64,
    pub open_pnl: f64,
    pub total_pnl: f64,
    pub closed_trades: u64,
    pub winning_trades: u64,
    pub losing_trades: u64,
    pub max_drawdown: Option<f64>,
    pub open_positions: Vec<OpenPosition>,
}

impl BotSnapshot {
    fn unreachable(url: &str, error: String) -> Self {
        Self {
            url: url.to_string(),
            reachable: false,
            error: Some(error),
            dry_run: None,
            live_tripwire: false,
            state: None,
            strategy: None,
            stake_currency: None,
            balance: None,
            closed_pnl: 0.0,
            open_pnl: 0.0,
            total_pnl: 0.0,
            closed_trades: 0,
            winning_trades: 0,
            losing_trades: 0,
            max_drawdown: None,
            open_positions: Vec::new(),
        }
    }
}

struct CachedToken {
    token: String,
    fetched_at: Instant,
}

fn token_cache() -> &'static Mutex<HashMap<String, CachedToken>> {
    static CACHE: OnceLock<Mutex<HashMap<String, CachedToken>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

#[derive(Clone, Serialize)]
pub struct EnvReady {
    pub env_exists: bool,
    pub username_set: bool,
    pub password_set: bool,
}

#[derive(Clone, Serialize)]
pub struct FleetEntry {
    pub label: String,
    pub snapshot: BotSnapshot,
}

pub fn catalog() -> Vec<BotInfo> {
    catalog_local()
}

pub fn catalog_local() -> Vec<BotInfo> {
    BOT_DEFS
        .iter()
        .map(|b| BotInfo {
            url: format!("http://127.0.0.1:{}", b.local_port),
            slug: b.slug.into(),
            label: b.label.into(),
            strategy: b.strategy.into(),
        })
        .collect()
}

/// Build the Caddy-fronted fleet for a validated `https://host` origin.
pub fn catalog_remote(origin: &str) -> Result<Vec<BotInfo>, String> {
    let origin = normalize_remote_origin(origin)?;
    Ok(BOT_DEFS
        .iter()
        .map(|b| BotInfo {
            url: format!("{origin}/bot/{}", b.slug),
            slug: b.slug.into(),
            label: b.label.into(),
            strategy: b.strategy.into(),
        })
        .collect())
}

/// `https://hostname` only — no path, userinfo, IP literal, or non-443 port.
pub fn normalize_remote_origin(origin: &str) -> Result<String, String> {
    let raw = origin.trim().trim_end_matches('/');
    let parsed = url::Url::parse(raw).map_err(|_| {
        "remote origin must look like https://trade.example.com".to_string()
    })?;
    if parsed.scheme() != "https" {
        return Err("remote origin must be https:// (TLS)".into());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("remote origin must not include credentials".into());
    }
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("remote origin must not include query or fragment".into());
    }
    if parsed.path() != "/" && !parsed.path().is_empty() {
        return Err("enter the site origin only (no /bot/… path)".into());
    }
    if let Some(port) = parsed.port() {
        if port != 443 {
            return Err("remote origin must use HTTPS on port 443".into());
        }
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| "remote origin is missing a hostname".to_string())?
        .trim_end_matches('.')
        .to_ascii_lowercase();
    if !is_public_hostname(&host) {
        return Err("remote origin must be a public hostname (not localhost or a raw IP)".into());
    }
    Ok(format!("https://{host}"))
}

fn is_public_hostname(host: &str) -> bool {
    let host = host.trim_end_matches('.').to_ascii_lowercase();
    if host.is_empty() || host == "localhost" || !host.is_ascii() {
        return false;
    }
    // Homograph / IDN hosts — require the operator to use the ASCII form we can audit.
    if host.contains("xn--") {
        return false;
    }
    if host.parse::<IpAddr>().is_ok() {
        return false;
    }
    if !host.contains('.') || host.starts_with('.') || host.ends_with('.') || host.contains("..") {
        return false;
    }
    if BLOCKED_HOST_SUFFIXES.iter().any(|s| host.ends_with(s)) {
        return false;
    }
    let labels: Vec<&str> = host.split('.').collect();
    if labels.len() < 2 || host.len() > 253 {
        return false;
    }
    let Some(tld) = labels.last() else {
        return false;
    };
    if tld.len() < 2 || !tld.bytes().all(|b| b.is_ascii_lowercase()) {
        return false;
    }
    labels.iter().all(|label| is_dns_label(label))
}

fn is_dns_label(label: &str) -> bool {
    let b = label.as_bytes();
    if b.is_empty() || b.len() > 63 {
        return false;
    }
    if !b[0].is_ascii_alphanumeric() || !b[b.len() - 1].is_ascii_alphanumeric() {
        return false;
    }
    b.iter()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == b'-')
}

/// Snapshot URLs in remote mode must be on the *saved* origin — not any public host.
pub fn bind_remote_bot_url(url: &str, origin: &str) -> Result<String, String> {
    let origin = normalize_remote_origin(origin)?;
    let url = allowed_bot_url(url)?;
    let prefix = format!("{origin}/bot/");
    if !url.starts_with(&prefix) {
        return Err("bot URL is not on the saved remote origin".into());
    }
    Ok(url)
}

/// Browser-open allowlist. Never pass webview strings through `open::that`.
pub fn is_allowed_open_url(url: &str) -> bool {
    matches!(
        url,
        "http://127.0.0.1:8899"
            | "http://127.0.0.1:8080"
            | "https://pro.kraken.com/app/settings/api"
            | "https://docs.docker.com/desktop/setup/install/mac-install/"
            | "https://docs.docker.com/desktop/setup/install/windows-install/"
            | "https://docs.docker.com/engine/install/"
    ) || allowed_remote_cockpit_url(url).is_ok()
}

fn allowed_remote_cockpit_url(url: &str) -> Result<String, String> {
    let parsed = url::Url::parse(url.trim()).map_err(|_| "invalid open URL".to_string())?;
    if parsed.scheme() != "https" {
        return Err("open URL must be https".into());
    }
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("open URL must not include query or fragment".into());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("open URL must not include credentials".into());
    }
    if let Some(port) = parsed.port() {
        if port != 443 {
            return Err("open URL must use port 443".into());
        }
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| "open URL missing host".to_string())?
        .trim_end_matches('.')
        .to_ascii_lowercase();
    if !is_public_hostname(&host) {
        return Err("open URL host is not a public hostname".into());
    }
    let path = parsed.path().trim_end_matches('/');
    if path.is_empty() || path == "/" || path == "/frequi" {
        return Ok(format!(
            "https://{host}{}",
            if path == "/frequi" { "/frequi" } else { "" }
        ));
    }
    Err("open URL path is not allowlisted".into())
}

pub fn remote_cockpit_url(origin: &str) -> Result<String, String> {
    let origin = normalize_remote_origin(origin)?;
    if !is_allowed_open_url(&origin) {
        return Err("refusing to open a non-allowlisted cockpit URL".into());
    }
    Ok(origin)
}

pub fn remote_frequi_url(origin: &str) -> Result<String, String> {
    let origin = normalize_remote_origin(origin)?;
    let url = format!("{origin}/frequi");
    if !is_allowed_open_url(&url) {
        return Err("refusing to open a non-allowlisted FreqUI URL".into());
    }
    Ok(url)
}

/// Refuse secrets that could inject HTTP headers or `.env` lines.
pub fn validate_secret_value(label: &str, value: &str, max_len: usize) -> Result<(), String> {
    if value.is_empty() {
        return Err(format!("{label} is required"));
    }
    if value.len() > max_len {
        return Err(format!("{label} is too long"));
    }
    if value.bytes().any(|b| b < 0x20 || b == 0x7f) {
        return Err(format!("{label} contains control characters"));
    }
    Ok(())
}

/// Compose / `.env` writes only happen inside a folder that looks like Voltra.
pub fn validate_voltra_project(dir: &Path) -> Result<PathBuf, String> {
    if dir.as_os_str().is_empty() {
        return Err("project folder is empty".into());
    }
    let meta = fs::metadata(dir).map_err(|_| {
        "project folder does not exist — pick the Voltra checkout with docker-compose.yml".to_string()
    })?;
    if !meta.is_dir() {
        return Err("project path is not a folder".into());
    }
    let canonical = fs::canonicalize(dir).map_err(|e| format!("could not resolve project folder: {e}"))?;
    if !canonical.join("docker-compose.yml").is_file() {
        return Err("folder must contain docker-compose.yml (Voltra checkout)".into());
    }
    Ok(canonical)
}

pub fn restrict_env_file_permissions(path: &Path) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(meta) = fs::metadata(path) {
            let mut perms = meta.permissions();
            perms.set_mode(0o600);
            let _ = fs::set_permissions(path, perms);
        }
    }
}

fn is_globally_routable(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(v) => {
            let o = v.octets();
            let cgnat = o[0] == 100 && (o[1] & 0xc0) == 64;
            !v.is_unspecified()
                && !v.is_loopback()
                && !v.is_private()
                && !v.is_link_local()
                && !v.is_broadcast()
                && !v.is_multicast()
                && !v.is_documentation()
                && !cgnat
                && o[0] != 0
        }
        IpAddr::V6(v) => {
            !v.is_unspecified()
                && !v.is_loopback()
                && !v.is_multicast()
                && !v.is_unique_local()
                && !v.is_unicast_link_local()
                && v.to_ipv4_mapped().is_none_or(|m| is_globally_routable(IpAddr::V4(m)))
        }
    }
}

fn assert_https_peer_is_public(base: &str) -> Result<(), String> {
    let parsed = url::Url::parse(base).map_err(|_| "invalid bot URL".to_string())?;
    if parsed.scheme() != "https" {
        return Ok(());
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| "bot URL missing host".to_string())?;
    use std::net::ToSocketAddrs;
    let addrs = (host, 443)
        .to_socket_addrs()
        .map_err(|_| format!("could not resolve {host}"))?;
    let mut any = false;
    for addr in addrs {
        any = true;
        if !is_globally_routable(addr.ip()) {
            return Err("remote host resolves to a private or local address".into());
        }
    }
    if !any {
        return Err(format!("could not resolve {host}"));
    }
    Ok(())
}

/// Local `http://127.0.0.1:<port>` **or** `https://host/bot/<slug>`.
pub fn allowed_bot_url(url: &str) -> Result<String, String> {
    let url = url.trim().trim_end_matches('/');
    let parsed = url::Url::parse(url).map_err(|_| "invalid bot URL".to_string())?;
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("bot URL must not include query or fragment".into());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("bot URL must not include credentials".into());
    }
    match parsed.scheme() {
        "http" => allowed_local_url(&parsed),
        "https" => allowed_remote_bot_url(&parsed),
        _ => Err("bot URL must be http://127.0.0.1 or https://<domain>/bot/<slug>".into()),
    }
}

fn allowed_local_url(parsed: &url::Url) -> Result<String, String> {
    match parsed.host_str() {
        Some("127.0.0.1") | Some("localhost") => {}
        _ => return Err("http bot URL must be localhost (127.0.0.1)".into()),
    }
    if parsed.path() != "/" && !parsed.path().is_empty() {
        return Err("local bot URL must not include a path".into());
    }
    let port = parsed
        .port()
        .ok_or_else(|| "local bot URL must include a port".to_string())?;
    if !ALLOWED_PORTS.contains(&port) {
        return Err(format!("port {port} is not a known local bot"));
    }
    Ok(format!("http://127.0.0.1:{port}"))
}

fn allowed_remote_bot_url(parsed: &url::Url) -> Result<String, String> {
    if let Some(port) = parsed.port() {
        if port != 443 {
            return Err("remote bot URL must use HTTPS on port 443".into());
        }
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| "remote bot URL is missing a hostname".to_string())?
        .trim_end_matches('.')
        .to_ascii_lowercase();
    if !is_public_hostname(&host) {
        return Err("remote bot URL must be a public hostname".into());
    }
    let path = parsed.path().trim_end_matches('/');
    let Some(slug) = path.strip_prefix("/bot/") else {
        return Err("remote bot URL must be https://<domain>/bot/<slug>".into());
    };
    if slug.contains('/') || !REMOTE_SLUGS.contains(&slug) {
        return Err(format!("unknown remote bot slug '{slug}'"));
    }
    Ok(format!("https://{host}/bot/{slug}"))
}

fn peek_env_creds(env_text: &str) -> (Option<String>, Option<String>) {
    let mut user = None;
    let mut pass = None;
    for raw in env_text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let value = strip_quotes(value.trim());
        match key.trim() {
            "FREQTRADE__API_SERVER__USERNAME" => user = Some(value),
            "FREQTRADE__API_SERVER__PASSWORD" => pass = Some(value),
            _ => {}
        }
    }
    (
        user.filter(|s| !s.is_empty()),
        pass.filter(|s| !s.is_empty()),
    )
}

pub fn parse_env_creds(env_text: &str) -> Result<(String, String), String> {
    let (user, pass) = peek_env_creds(env_text);
    let user = user.ok_or_else(|| {
        "FREQTRADE__API_SERVER__USERNAME missing in .env".to_string()
    })?;
    let pass = pass.ok_or_else(|| {
        "FREQTRADE__API_SERVER__PASSWORD missing in .env — set the WebUI password".to_string()
    })?;
    validate_secret_value("WebUI username", &user, 128)?;
    validate_secret_value("WebUI password", &pass, 256)?;
    Ok((user, pass))
}

fn strip_quotes(value: &str) -> String {
    let b = value.as_bytes();
    if b.len() >= 2
        && ((b[0] == b'"' && b[b.len() - 1] == b'"')
            || (b[0] == b'\'' && b[b.len() - 1] == b'\''))
    {
        return value[1..value.len() - 1].to_string();
    }
    value.to_string()
}

fn load_creds(project_dir: &Path) -> Result<(String, String), String> {
    let path = project_dir.join(".env");
    let text = fs::read_to_string(&path).map_err(|_| {
        format!(
            "could not read {} — copy .env.example to .env and set the WebUI password",
            path.display()
        )
    })?;
    parse_env_creds(&text)
}

fn basic_auth(user: &str, pass: &str) -> String {
    use base64::{engine::general_purpose::STANDARD, Engine as _};
    STANDARD.encode(format!("{user}:{pass}"))
}

fn http_agent() -> ureq::Agent {
    // Never follow redirects — a 302 would forward Authorization to a new host.
    ureq::AgentBuilder::new()
        .timeout(REQUEST_TIMEOUT)
        .redirects(0)
        .build()
}

fn response_json(resp: ureq::Response, what: &str) -> Result<Value, String> {
    let mut buf = Vec::new();
    resp.into_reader()
        .take(MAX_JSON_BODY + 1)
        .read_to_end(&mut buf)
        .map_err(|e| format!("{what}: {e}"))?;
    if buf.len() as u64 > MAX_JSON_BODY {
        return Err(format!("{what}: response too large"));
    }
    serde_json::from_slice(&buf).map_err(|e| format!("{what}: {e}"))
}

fn sanitize_access_token(token: &str) -> Result<String, String> {
    let token = token.trim();
    if token.is_empty() || token.len() > 8192 {
        return Err("login returned an invalid access_token".into());
    }
    let ok = token.bytes().all(|b| {
        b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-' | b'+' | b'/' | b'=')
    });
    if !ok {
        return Err("login returned an invalid access_token".into());
    }
    Ok(token.to_string())
}

fn login(base: &str, user: &str, pass: &str) -> Result<String, String> {
    validate_secret_value("WebUI username", user, 128)?;
    validate_secret_value("WebUI password", pass, 256)?;
    let resp = match http_agent()
        .post(&format!("{base}{LOGIN_PATH}"))
        .set("Authorization", &format!("Basic {}", basic_auth(user, pass)))
        .call()
    {
        Ok(r) if r.status() == 200 => r,
        Ok(r) => return Err(format!("login failed (HTTP {})", r.status())),
        Err(ureq::Error::Status(401, _)) => {
            return Err(
                "login failed (HTTP 401) — check the FreqUI / WebUI password".into(),
            );
        }
        Err(ureq::Error::Status(code, _)) => {
            return Err(format!("login failed (HTTP {code})"));
        }
        Err(e) => return Err(format!("login failed: {e}")),
    };
    let body = response_json(resp, "login response")?;
    let token = body
        .get("access_token")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "login response missing access_token".to_string())?;
    sanitize_access_token(token)
}

fn creds_cache_key(base: &str, user: &str, pass: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(base.as_bytes());
    hasher.update([0xff]);
    hasher.update(user.as_bytes());
    hasher.update([0xff]);
    hasher.update(pass.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn allowlisted_get_path(path: &str) -> Result<&'static str, String> {
    GET_PATHS
        .iter()
        .copied()
        .find(|p| *p == path)
        .ok_or_else(|| "internal: refused non-allowlisted API path".to_string())
}

fn cached_token(base: &str, user: &str, pass: &str) -> Result<String, String> {
    let key = creds_cache_key(base, user, pass);
    {
        let cache = token_cache().lock().map_err(|e| e.to_string())?;
        if let Some(tok) = cache.get(&key) {
            if tok.fetched_at.elapsed() < TOKEN_TTL {
                return Ok(tok.token.clone());
            }
        }
    }
    let token = login(base, user, pass)?;
    if let Ok(mut cache) = token_cache().lock() {
        cache.insert(
            key,
            CachedToken {
                token: token.clone(),
                fetched_at: Instant::now(),
            },
        );
    }
    Ok(token)
}

fn invalidate_token(base: &str, user: &str, pass: &str) {
    if let Ok(mut cache) = token_cache().lock() {
        cache.remove(&creds_cache_key(base, user, pass));
    }
}

fn get_json(base: &str, path: &str, token: &str) -> Result<(u16, Value), String> {
    let path = allowlisted_get_path(path)?;
    let resp = match http_agent()
        .get(&format!("{base}/api/v1{path}"))
        .set("Authorization", &format!("Bearer {token}"))
        .call()
    {
        Ok(r) => r,
        Err(ureq::Error::Status(code, _)) => return Ok((code, Value::Null)),
        Err(e) => return Err(format!("{path}: {e}")),
    };
    let status = resp.status();
    if !(200..300).contains(&status) {
        return Ok((status, Value::Null));
    }
    Ok((status, response_json(resp, path)?))
}

fn get_json_authed(
    base: &str,
    path: &str,
    user: &str,
    pass: &str,
) -> Result<Value, String> {
    let token = cached_token(base, user, pass)?;
    let (status, body) = get_json(base, path, &token)?;
    if status == 401 {
        invalidate_token(base, user, pass);
        let token = cached_token(base, user, pass)?;
        let (status, body) = get_json(base, path, &token)?;
        if status == 401 {
            return Err("unauthorized — WebUI password rejected".into());
        }
        if !(200..300).contains(&status) {
            return Err(format!("{path} → HTTP {status}"));
        }
        return Ok(body);
    }
    if !(200..300).contains(&status) {
        return Err(format!("{path} → HTTP {status}"));
    }
    Ok(body)
}

fn f64_field(v: &Value, keys: &[&str]) -> Option<f64> {
    for k in keys {
        let Some(x) = v.get(*k) else { continue };
        if let Some(n) = x.as_f64() {
            return Some(n);
        }
        if let Some(n) = x.as_i64() {
            return Some(n as f64);
        }
        if let Some(n) = x.as_u64() {
            return Some(n as f64);
        }
        if let Some(s) = x.as_str() {
            if let Ok(n) = s.parse::<f64>() {
                return Some(n);
            }
        }
    }
    None
}

fn u64_field(v: &Value, key: &str) -> u64 {
    v.get(key)
        .and_then(|x| x.as_u64().or_else(|| x.as_i64().map(|n| n.max(0) as u64)))
        .unwrap_or(0)
}

pub fn positions_from_status(status: &Value) -> Vec<OpenPosition> {
    let arr: Vec<Value> = match status {
        Value::Array(a) => a.clone(),
        other => other
            .get("data")
            .and_then(|d| d.as_array())
            .cloned()
            .unwrap_or_default(),
    };
    arr.iter()
        .filter_map(|t| {
            let pair = t.get("pair")?.as_str()?.to_string();
            Some(OpenPosition {
                pair,
                profit_abs: f64_field(t, &["profit_abs"]).unwrap_or(0.0),
                profit_ratio: f64_field(t, &["profit_ratio"]).unwrap_or(0.0),
                open_rate: f64_field(t, &["open_rate"]),
                amount: f64_field(t, &["amount"]),
            })
        })
        .collect()
}

pub fn snapshot_from_payloads(
    url: &str,
    cfg: &Value,
    profit: &Value,
    balance: &Value,
    status: &Value,
) -> BotSnapshot {
    let positions = positions_from_status(status);
    let closed_pnl = f64_field(profit, &["profit_closed_coin"]).unwrap_or(0.0);
    let open_pnl: f64 = positions.iter().map(|p| p.profit_abs).sum();
    let dry_run = cfg.get("dry_run").and_then(|v| v.as_bool());
    BotSnapshot {
        url: url.to_string(),
        reachable: true,
        error: None,
        dry_run,
        live_tripwire: dry_run == Some(false),
        state: cfg.get("state").and_then(|v| v.as_str()).map(|s| s.to_string()),
        strategy: cfg
            .get("strategy")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        stake_currency: cfg
            .get("stake_currency")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        balance: f64_field(balance, &["total_bot", "total"]),
        closed_pnl,
        open_pnl,
        total_pnl: closed_pnl + open_pnl,
        closed_trades: u64_field(profit, "closed_trade_count"),
        winning_trades: u64_field(profit, "winning_trades"),
        losing_trades: u64_field(profit, "losing_trades"),
        max_drawdown: f64_field(profit, &["max_drawdown"]),
        open_positions: positions,
    }
}

pub fn inspect_env(project_dir: &Path) -> EnvReady {
    let path = project_dir.join(".env");
    let Ok(text) = fs::read_to_string(&path) else {
        return EnvReady {
            env_exists: false,
            username_set: false,
            password_set: false,
        };
    };
    let (user, pass) = peek_env_creds(&text);
    EnvReady {
        env_exists: true,
        username_set: user.is_some(),
        password_set: pass.is_some(),
    }
}

/// Human-readable stack gate for the controller banner. Never mentions secrets.
pub fn stack_ready_hint(
    cli_found: bool,
    daemon_ok: bool,
    compose_file: bool,
    env: &EnvReady,
) -> (bool, String) {
    if !cli_found {
        return (
            false,
            "Docker CLI not found. Install Docker Desktop, then Start stack.".into(),
        );
    }
    if !daemon_ok {
        return (
            false,
            "Docker is installed but the daemon is not running — start Docker Desktop.".into(),
        );
    }
    if !compose_file {
        return (
            false,
            "This folder has no docker-compose.yml — pick the Voltra checkout.".into(),
        );
    }
    if !env.env_exists {
        return (
            false,
            "No .env yet — copy from .env.example, then set the WebUI password.".into(),
        );
    }
    if !env.password_set {
        return (
            false,
            "Set FREQTRADE__API_SERVER__PASSWORD in .env so the live snapshot can log in.".into(),
        );
    }
    (true, "Docker ready. Snapshot stays read-only; dry-run is never flipped.".into())
}

pub fn fetch_fleet(project_dir: &Path) -> Vec<FleetEntry> {
    fetch_fleet_from(&catalog_local(), &load_creds(project_dir))
}

pub fn fetch_fleet_from(
    bots: &[BotInfo],
    creds: &Result<(String, String), String>,
) -> Vec<FleetEntry> {
    match creds {
        Err(e) => bots
            .iter()
            .map(|bot| FleetEntry {
                snapshot: BotSnapshot::unreachable(&bot.url, e.clone()),
                label: bot.label.clone(),
            })
            .collect(),
        Ok((user, pass)) => bots
            .iter()
            .map(|bot| FleetEntry {
                snapshot: fetch_snapshot_with_creds(&bot.url, user, pass)
                    .unwrap_or_else(|e| BotSnapshot::unreachable(&bot.url, e)),
                label: bot.label.clone(),
            })
            .collect(),
    }
}

pub fn fetch_snapshot(project_dir: &Path, url: &str) -> Result<BotSnapshot, String> {
    let (user, pass) = load_creds(project_dir)?;
    fetch_snapshot_with_creds(url, &user, &pass)
}

pub fn fetch_snapshot_with_creds(
    url: &str,
    user: &str,
    pass: &str,
) -> Result<BotSnapshot, String> {
    let base = allowed_bot_url(url)?;
    if let Err(e) = assert_https_peer_is_public(&base) {
        return Ok(BotSnapshot::unreachable(&base, e));
    }
    match fetch_snapshot_authed(&base, user, pass) {
        Ok(snap) => Ok(snap),
        Err(e) => Ok(BotSnapshot::unreachable(&base, e)),
    }
}

/// Remote snapshots must target the saved origin (stops sending WebUI creds elsewhere).
pub fn fetch_snapshot_on_origin(
    origin: &str,
    url: &str,
    user: &str,
    pass: &str,
) -> Result<BotSnapshot, String> {
    let url = bind_remote_bot_url(url, origin)?;
    fetch_snapshot_with_creds(&url, user, pass)
}

fn fetch_snapshot_authed(base: &str, user: &str, pass: &str) -> Result<BotSnapshot, String> {
    let cfg = get_json_authed(base, "/show_config", user, pass)?;
    let profit = get_json_authed(base, "/profit", user, pass)?;
    let balance = get_json_authed(base, "/balance", user, pass)?;
    let status = get_json_authed(base, "/status", user, pass)?;
    Ok(snapshot_from_payloads(base, &cfg, &profit, &balance, &status))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn allowlist_accepts_known_local_bots() {
        assert_eq!(
            allowed_bot_url("http://127.0.0.1:8080/").unwrap(),
            "http://127.0.0.1:8080"
        );
        assert!(allowed_bot_url("http://localhost:8084").is_ok());
        assert_eq!(
            allowed_bot_url("http://localhost:8084").unwrap(),
            "http://127.0.0.1:8084"
        );
    }

    #[test]
    fn allowlist_rejects_remote_http_and_unknown_ports() {
        assert!(allowed_bot_url("http://example.com:8080").is_err());
        assert!(allowed_bot_url("https://127.0.0.1:8080").is_err());
        assert!(allowed_bot_url("http://127.0.0.1:22").is_err());
        assert!(allowed_bot_url("http://10.0.0.5:8080").is_err());
        assert!(allowed_bot_url("http://127.0.0.1:8080/api/v1").is_err());
    }

    #[test]
    fn normalize_origin_requires_https_public_host() {
        assert_eq!(
            normalize_remote_origin("https://Trade.Example.COM/").unwrap(),
            "https://trade.example.com"
        );
        assert!(normalize_remote_origin("http://trade.example.com").is_err());
        assert!(normalize_remote_origin("https://127.0.0.1").is_err());
        assert!(normalize_remote_origin("https://localhost").is_err());
        assert!(normalize_remote_origin("https://8.8.8.8").is_err());
        assert!(normalize_remote_origin("https://user:pw@trade.example.com").is_err());
        assert!(normalize_remote_origin("https://trade.example.com/bot/dry").is_err());
        assert!(normalize_remote_origin("https://trade.example.com:8443").is_err());
        assert_eq!(
            normalize_remote_origin("https://trade.example.com.").unwrap(),
            "https://trade.example.com"
        );
    }

    #[test]
    fn allowlist_accepts_caddy_bot_paths() {
        assert_eq!(
            allowed_bot_url("https://trade.example.com/bot/dry/").unwrap(),
            "https://trade.example.com/bot/dry"
        );
        assert!(allowed_bot_url("https://trade.example.com/bot/xsmom").is_ok());
        assert!(allowed_bot_url("https://trade.example.com/bot/dca").is_ok());
    }

    #[test]
    fn allowlist_rejects_unknown_remote_slugs_and_http() {
        assert!(allowed_bot_url("https://trade.example.com/bot/admin").is_err());
        assert!(allowed_bot_url("https://trade.example.com/frequi").is_err());
        assert!(allowed_bot_url("https://trade.example.com/bot/dry/api/v1").is_err());
        assert!(allowed_bot_url("http://trade.example.com/bot/dry").is_err());
        assert!(allowed_bot_url("https://user:pw@trade.example.com/bot/dry").is_err());
        assert!(allowed_bot_url("https://xn--fsq.com/bot/dry").is_err());
        assert!(allowed_bot_url("https://bot.local/bot/dry").is_err());
        assert!(allowed_bot_url("https://trade.example.internal/bot/dry").is_err());
        assert!(allowed_bot_url("http://[::1]:8080").is_err());
    }

    #[test]
    fn remote_snapshot_url_must_match_saved_origin() {
        assert_eq!(
            bind_remote_bot_url("https://trade.example.com/bot/dry", "https://trade.example.com")
                .unwrap(),
            "https://trade.example.com/bot/dry"
        );
        assert!(bind_remote_bot_url(
            "https://evil.example.com/bot/dry",
            "https://trade.example.com"
        )
        .is_err());
        assert!(is_allowed_open_url("https://trade.example.com/frequi"));
        assert!(is_allowed_open_url("http://127.0.0.1:8899"));
        assert!(!is_allowed_open_url("https://evil.example.com/steal"));
        assert!(!is_allowed_open_url("javascript:alert(1)"));
        assert_eq!(
            remote_frequi_url("https://trade.example.com").unwrap(),
            "https://trade.example.com/frequi"
        );
    }

    #[test]
    fn secrets_and_project_dir_reject_unsafe_input() {
        assert!(validate_secret_value("password", "ok-secret", 32).is_ok());
        assert!(validate_secret_value("password", "bad\nsecret", 32).is_err());
        assert!(validate_secret_value("password", "bad\rsecret", 32).is_err());
        assert!(validate_secret_value("password", "", 32).is_err());
        let tmp = std::env::temp_dir().join(format!("voltra-proj-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&tmp);
        assert!(validate_voltra_project(&tmp).is_err());
        std::fs::write(tmp.join("docker-compose.yml"), "services: {}\n").unwrap();
        assert!(validate_voltra_project(&tmp).is_ok());
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn remote_catalog_uses_caddy_slugs() {
        let bots = catalog_remote("https://trade.example.com").unwrap();
        assert_eq!(bots.len(), 5);
        assert!(bots.iter().any(|b| b.slug == "dry" && b.url.ends_with("/bot/dry")));
        assert!(bots.iter().any(|b| b.url == "https://trade.example.com/bot/xsmom"));
        assert!(bots.iter().all(|b| b.url.starts_with("https://trade.example.com/bot/")));
    }

    #[test]
    fn parses_env_creds_and_quotes() {
        let env = "\
# comment
FREQTRADE__API_SERVER__USERNAME=voltra
FREQTRADE__API_SERVER__PASSWORD=\"s3cret\"
OTHER=ignore
";
        let (u, p) = parse_env_creds(env).unwrap();
        assert_eq!((u, p), ("voltra".into(), "s3cret".into()));
    }

    #[test]
    fn rejects_empty_password() {
        let env = "FREQTRADE__API_SERVER__USERNAME=voltra\nFREQTRADE__API_SERVER__PASSWORD=\n";
        assert!(parse_env_creds(env).unwrap_err().contains("PASSWORD"));
    }

    #[test]
    fn snapshot_adds_open_pnl_to_closed() {
        let cfg = json!({"dry_run": true, "state": "running", "strategy": "TrendBreakStrategy", "stake_currency": "USD"});
        let profit = json!({
            "profit_closed_coin": 12.5,
            "closed_trade_count": 4,
            "winning_trades": 3,
            "losing_trades": 1,
            "max_drawdown": 0.04
        });
        let balance = json!({"total": 5012.5, "total_bot": 5012.5});
        let status = json!([
            {"pair": "BTC/USD", "profit_abs": 3.0, "profit_ratio": 0.02, "open_rate": 60000.0, "amount": 0.01},
            {"pair": "ETH/USD", "profit_abs": -1.5, "profit_ratio": -0.01, "open_rate": 3000.0, "amount": 0.2}
        ]);
        let snap = snapshot_from_payloads("http://127.0.0.1:8080", &cfg, &profit, &balance, &status);
        assert!(snap.reachable);
        assert_eq!(snap.dry_run, Some(true));
        assert!(!snap.live_tripwire);
        assert_eq!(snap.closed_pnl, 12.5);
        assert_eq!(snap.open_pnl, 1.5);
        assert_eq!(snap.total_pnl, 14.0);
        assert_eq!(snap.open_positions.len(), 2);
        assert_eq!(snap.closed_trades, 4);
        assert_eq!(snap.balance, Some(5012.5));
    }

    #[test]
    fn inspect_env_reports_partial_creds() {
        let tmp = std::env::temp_dir().join(format!("voltra-env-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&tmp);
        std::fs::write(tmp.join(".env"), "FREQTRADE__API_SERVER__USERNAME=voltra\n").unwrap();
        let ready = inspect_env(&tmp);
        assert!(ready.env_exists && ready.username_set && !ready.password_set);
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn stack_ready_hint_prioritizes_docker_then_env() {
        let missing_pw = EnvReady {
            env_exists: true,
            username_set: true,
            password_set: false,
        };
        let (ok, hint) = stack_ready_hint(true, true, true, &missing_pw);
        assert!(!ok);
        assert!(hint.contains("PASSWORD"));
        let ready = EnvReady {
            env_exists: true,
            username_set: true,
            password_set: true,
        };
        assert!(stack_ready_hint(true, true, true, &ready).0);
        assert!(!stack_ready_hint(false, false, true, &ready).0);
    }

    #[test]
    fn snapshot_flags_live_tripwire() {
        let cfg = json!({"dry_run": false, "state": "running", "strategy": "X"});
        let snap = snapshot_from_payloads(
            "http://127.0.0.1:8080",
            &cfg,
            &json!({}),
            &json!({}),
            &json!([]),
        );
        assert!(snap.live_tripwire);
        assert_eq!(snap.dry_run, Some(false));
    }

    #[test]
    fn snapshot_parses_string_profit_numbers() {
        let profit = json!({"profit_closed_coin": "2.5", "closed_trade_count": 1});
        let status = json!([{"pair": "SOL/USD", "profit_abs": "1.25", "profit_ratio": "0.01"}]);
        let snap = snapshot_from_payloads(
            "http://127.0.0.1:8080",
            &json!({"dry_run": true, "state": "running"}),
            &profit,
            &json!({"total": "100"}),
            &status,
        );
        assert_eq!(snap.closed_pnl, 2.5);
        assert_eq!(snap.open_pnl, 1.25);
        assert_eq!(snap.balance, Some(100.0));
    }

    #[test]
    fn jwt_snapshot_against_local_mock_http() {
        let port = spawn_freqtrade_mock().expect("bind a local allowlisted bot port for the mock");
        let url = format!("http://127.0.0.1:{port}");
        let snap = fetch_snapshot_with_creds(&url, "voltra", "s3cret").unwrap();
        assert!(snap.reachable, "{:?}", snap.error);
        assert_eq!(snap.dry_run, Some(true));
        assert!(!snap.live_tripwire);
        assert_eq!(snap.closed_pnl, 4.0);
        assert_eq!(snap.strategy.as_deref(), Some("TrendBreakStrategy"));

        let denied = fetch_snapshot_with_creds(&url, "voltra", "wrong").unwrap();
        assert!(
            !denied.reachable,
            "wrong password must not reuse a prior JWT: {denied:?}"
        );
        assert!(
            denied.error.as_deref().unwrap_or("").contains("401"),
            "{:?}",
            denied.error
        );
    }

    #[test]
    fn jwt_login_does_not_follow_redirects() {
        let port = spawn_redirect_mock().expect("bind a local allowlisted bot port for the redirect mock");
        let url = format!("http://127.0.0.1:{port}");
        let snap = fetch_snapshot_with_creds(&url, "voltra", "s3cret").unwrap();
        assert!(!snap.reachable, "{:?}", snap.error);
        let err = snap.error.unwrap_or_default();
        assert!(
            err.contains("302") || err.contains("login failed"),
            "{err}"
        );
    }

    fn spawn_redirect_mock() -> Option<u16> {
        use std::io::Write;
        use std::net::TcpListener;
        use std::thread;
        use std::time::Duration;

        let mut bound = None;
        for port in [8080_u16, 8081, 8082, 8083, 8084] {
            if let Ok(listener) = TcpListener::bind(("127.0.0.1", port)) {
                bound = Some((port, listener));
                break;
            }
        }
        let (port, listener) = bound?;
        let _ = listener.set_nonblocking(true);
        thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_secs(8);
            while Instant::now() < deadline {
                match listener.accept() {
                    Ok((mut stream, _)) => {
                        let _ = stream.set_nonblocking(false);
                        let _ = read_http_head(&mut stream);
                        let body = "{}";
                        let resp = format!(
                            "HTTP/1.1 302 Found\r\nLocation: https://evil.example.com/steal\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                            body.len()
                        );
                        let _ = stream.write_all(resp.as_bytes());
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(15));
                    }
                    Err(_) => break,
                }
            }
        });
        thread::sleep(Duration::from_millis(40));
        Some(port)
    }

    fn spawn_freqtrade_mock() -> Option<u16> {
        use std::io::Write;
        use std::net::TcpListener;
        use std::thread;
        use std::time::Duration;

        let mut bound = None;
        for port in [8083_u16, 8082, 8081, 8084, 8080] {
            if let Ok(listener) = TcpListener::bind(("127.0.0.1", port)) {
                bound = Some((port, listener));
                break;
            }
        }
        let (port, listener) = bound?;
        let _ = listener.set_nonblocking(true);
        thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_secs(8);
            while Instant::now() < deadline {
                match listener.accept() {
                    Ok((mut stream, _)) => {
                        let _ = stream.set_nonblocking(false);
                        let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
                        let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
                        let req = match read_http_head(&mut stream) {
                            Ok(req) => req,
                            Err(_) => continue,
                        };
                        let (status, body) = mock_freqtrade_response(&req);
                        let resp = format!(
                            "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                            body.len()
                        );
                        let _ = stream.write_all(resp.as_bytes());
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(15));
                    }
                    Err(_) => break,
                }
            }
        });
        thread::sleep(Duration::from_millis(40));
        Some(port)
    }

    fn read_http_head(stream: &mut std::net::TcpStream) -> std::io::Result<String> {
        use std::io::Read;
        let mut buf = Vec::new();
        let mut tmp = [0u8; 1024];
        loop {
            let n = stream.read(&mut tmp)?;
            if n == 0 {
                break;
            }
            buf.extend_from_slice(&tmp[..n]);
            if buf.windows(4).any(|w| w == b"\r\n\r\n") || buf.windows(2).any(|w| w == b"\n\n") {
                break;
            }
            if buf.len() > 16 * 1024 {
                break;
            }
        }
        Ok(String::from_utf8_lossy(&buf).into_owned())
    }

    fn mock_freqtrade_response(req: &str) -> (&'static str, String) {
        use base64::{engine::general_purpose::STANDARD, Engine as _};
        let first = req.lines().next().unwrap_or("");
        let basic_ok = req.contains(&format!("Authorization: Basic {}", STANDARD.encode("voltra:s3cret")));
        let bearer_ok = req.contains("Authorization: Bearer test-token");
        if first.starts_with("POST /api/v1/token/login") {
            if basic_ok {
                return ("200 OK", r#"{"access_token":"test-token"}"#.into());
            }
            return ("401 Unauthorized", r#"{"detail":"Unauthorized"}"#.into());
        }
        if !bearer_ok {
            return ("401 Unauthorized", r#"{"detail":"Unauthorized"}"#.into());
        }
        if first.contains("/api/v1/show_config") {
            return (
                "200 OK",
                r#"{"dry_run":true,"state":"running","strategy":"TrendBreakStrategy","stake_currency":"USD"}"#.into(),
            );
        }
        if first.contains("/api/v1/profit") {
            return (
                "200 OK",
                r#"{"profit_closed_coin":4.0,"closed_trade_count":2,"winning_trades":2,"losing_trades":0,"max_drawdown":0.01}"#.into(),
            );
        }
        if first.contains("/api/v1/balance") {
            return ("200 OK", r#"{"total":1004.0,"total_bot":1004.0}"#.into());
        }
        if first.contains("/api/v1/status") {
            return ("200 OK", "[]".into());
        }
        ("404 Not Found", "{}".into())
    }
}
