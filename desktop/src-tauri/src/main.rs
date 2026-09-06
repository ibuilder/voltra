// Voltra desktop controller.
//
// A thin tray app that manages the Dockerized Voltra trading stack — it does
// NOT trade or hold strategy logic itself (that all lives in the Docker
// containers). It just: starts/stops the stack, reports status, opens the
// dashboard, and can enable run-on-login on its own.
//
// SAFETY: this app never sets dry_run=false or touches live-trading config.
// It only runs `docker compose up -d / down / ps` in the project directory
// and read-only Freqtrade REST (JWT snapshot of P&L / positions).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use freqtrade_client as freqtrade;

use std::path::PathBuf;
use std::process::Command;

use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_autostart::ManagerExt;

const DEFAULT_PROJECT_DIR: &str = "C:\\Server\\solsignal";

fn docker_candidates() -> &'static [&'static str] {
    &[
        "docker",
        "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe",
        "/usr/local/bin/docker",
        "/usr/bin/docker",
    ]
}

// Candidate docker CLI locations (Docker Desktop is often not on PATH).
fn docker_bin() -> Option<String> {
    for c in docker_candidates() {
        if Command::new(c).arg("--version").output().map(|o| o.status.success()).unwrap_or(false) {
            return Some((*c).to_string());
        }
    }
    None
}

fn docker_daemon_ok(bin: &str) -> bool {
    Command::new(bin)
        .args(["info", "--format", "{{.ServerVersion}}"])
        .output()
        .map(|o| o.status.success() && !String::from_utf8_lossy(&o.stdout).trim().is_empty())
        .unwrap_or(false)
}

fn project_dir(app: &tauri::AppHandle) -> PathBuf {
    // Persisted override lives next to the app config; else the default path.
    if let Ok(dir) = app.path().app_config_dir() {
        let f = dir.join("project_dir.txt");
        if let Ok(s) = std::fs::read_to_string(&f) {
            let s = s.trim();
            if !s.is_empty() {
                return PathBuf::from(s);
            }
        }
    }
    PathBuf::from(DEFAULT_PROJECT_DIR)
}

fn compose(app: &tauri::AppHandle, args: &[&str]) -> Result<String, String> {
    let bin = docker_bin().ok_or_else(|| {
        "Docker CLI not found. Install Docker Desktop, then try again.".to_string()
    })?;
    if !docker_daemon_ok(&bin) {
        return Err("Docker is installed but the daemon is not running — start Docker Desktop.".into());
    }
    let dir = project_dir(app);
    let out = Command::new(bin)
        .arg("compose")
        .args(args)
        .current_dir(&dir)
        .output()
        .map_err(|e| format!("failed to run docker: {e}"))?;
    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
    if out.status.success() {
        Ok(format!("{stdout}{stderr}"))
    } else {
        Err(format!("{stdout}{stderr}"))
    }
}

#[derive(Serialize)]
struct ServiceStatus {
    name: String,
    status: String,
}

#[tauri::command]
fn stack_up(app: tauri::AppHandle) -> Result<String, String> {
    compose(&app, &["up", "-d"])
}

#[tauri::command]
fn stack_down(app: tauri::AppHandle) -> Result<String, String> {
    compose(&app, &["down"])
}

#[tauri::command]
fn stack_status(app: tauri::AppHandle) -> Result<Vec<ServiceStatus>, String> {
    let raw = compose(&app, &["ps", "--format", "{{.Name}}|{{.Status}}"])?;
    let rows = raw
        .lines()
        .filter(|l| l.contains('|'))
        .map(|l| {
            let (name, status) = l.split_once('|').unwrap();
            ServiceStatus { name: name.trim().to_string(), status: status.trim().to_string() }
        })
        .collect();
    Ok(rows)
}

#[tauri::command]
fn get_project_dir(app: tauri::AppHandle) -> String {
    project_dir(&app).to_string_lossy().to_string()
}

#[tauri::command]
fn set_project_dir(app: tauri::AppHandle, dir: String) -> Result<(), String> {
    let cfg = app.path().app_config_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&cfg).map_err(|e| e.to_string())?;
    std::fs::write(cfg.join("project_dir.txt"), dir).map_err(|e| e.to_string())
}

#[tauri::command]
fn autostart_enabled(app: tauri::AppHandle) -> bool {
    app.autolaunch().is_enabled().unwrap_or(false)
}

#[tauri::command]
fn set_autostart(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let al = app.autolaunch();
    if enabled { al.enable() } else { al.disable() }.map_err(|e| e.to_string())
}

fn is_remote_mode(app: &tauri::AppHandle) -> bool {
    connection_mode(app) == "remote"
}

fn connection_mode(app: &tauri::AppHandle) -> String {
    read_app_file(app, "connection_mode.txt").unwrap_or_else(|| "local".into())
}

fn read_app_file(app: &tauri::AppHandle, name: &str) -> Option<String> {
    let dir = app.path().app_config_dir().ok()?;
    let s = std::fs::read_to_string(dir.join(name)).ok()?;
    let s = s.trim();
    if s.is_empty() { None } else { Some(s.to_string()) }
}

fn write_app_file(app: &tauri::AppHandle, name: &str, value: &str) -> Result<(), String> {
    let cfg = app.path().app_config_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&cfg).map_err(|e| e.to_string())?;
    std::fs::write(cfg.join(name), value).map_err(|e| e.to_string())
}

fn remote_origin(app: &tauri::AppHandle) -> Option<String> {
    read_app_file(app, "remote_origin.txt")
        .and_then(|o| freqtrade::normalize_remote_origin(&o).ok())
}

fn remote_creds() -> Result<(String, String), String> {
    let user = kr_entry("remote_webui_user")?
        .get_password()
        .map_err(|_| "Save the remote WebUI username and password first.".to_string())?;
    let pass = kr_entry("remote_webui_password")?
        .get_password()
        .map_err(|_| "Save the remote WebUI username and password first.".to_string())?;
    if user.trim().is_empty() || pass.trim().is_empty() {
        return Err("Save the remote WebUI username and password first.".into());
    }
    Ok((user, pass))
}

fn fleet_bots(app: &tauri::AppHandle) -> Result<Vec<freqtrade::BotInfo>, String> {
    if is_remote_mode(app) {
        let origin = remote_origin(app).ok_or_else(|| {
            "Set a remote origin like https://trade.example.com first.".to_string()
        })?;
        freqtrade::catalog_remote(&origin)
    } else {
        Ok(freqtrade::catalog_local())
    }
}

#[tauri::command]
fn open_dashboard(app: tauri::AppHandle) {
    let url = if is_remote_mode(&app) {
        remote_origin(&app).unwrap_or_else(|| "http://127.0.0.1:8899".into())
    } else {
        "http://127.0.0.1:8899".into()
    };
    let _ = open::that(url);
}

#[tauri::command]
fn open_frequi(app: tauri::AppHandle) {
    let url = if is_remote_mode(&app) {
        remote_origin(&app)
            .map(|o| format!("{o}/frequi"))
            .unwrap_or_else(|| "http://127.0.0.1:8080".into())
    } else {
        "http://127.0.0.1:8080".into()
    };
    let _ = open::that(url);
}

// ---------------------------------------------------------------------------
// Kraken API key handling.
//
// Kraken has NO OAuth flow to provision keys for third-party apps, so the user
// creates a key by hand on Kraken's site (the "Open Kraken API page" button
// deep-links there) and pastes it in. We store it in the OS credential store
// (Windows Credential Manager) via `keyring` — never in a plaintext file.
//
// SAFETY: saving a key does NOT enable live trading. `dry_run` lives in the
// Docker config and is a human-only change; this app never touches it. The key
// only matters once the user manually goes live outside this app.
// ---------------------------------------------------------------------------
const KEYRING_SERVICE: &str = "voltra-controller";

fn kr_entry(name: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(KEYRING_SERVICE, name).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_kraken_key(key: String, secret: String) -> Result<(), String> {
    let (key, secret) = (key.trim(), secret.trim());
    if key.is_empty() || secret.is_empty() {
        return Err("Both the API key and secret are required.".into());
    }
    kr_entry("kraken_api_key")?
        .set_password(key)
        .map_err(|e| format!("could not save key: {e}"))?;
    kr_entry("kraken_api_secret")?
        .set_password(secret)
        .map_err(|e| format!("could not save secret: {e}"))?;
    Ok(())
}

#[derive(Serialize)]
struct KeyStatus {
    saved: bool,
    hint: String,
}

#[tauri::command]
fn kraken_key_status() -> KeyStatus {
    match kr_entry("kraken_api_key").and_then(|e| e.get_password().map_err(|e| e.to_string())) {
        Ok(k) if !k.is_empty() => {
            // Show only a masked fingerprint, never the full secret, to the UI.
            let hint = if k.len() > 8 {
                format!("{}…{}", &k[..4], &k[k.len() - 4..])
            } else {
                "saved".into()
            };
            KeyStatus { saved: true, hint }
        }
        _ => KeyStatus { saved: false, hint: String::new() },
    }
}

#[tauri::command]
fn clear_kraken_key() -> Result<(), String> {
    // Remove both entries; a missing entry is not an error.
    if let Ok(e) = kr_entry("kraken_api_key") {
        let _ = e.delete_password();
    }
    if let Ok(e) = kr_entry("kraken_api_secret") {
        let _ = e.delete_password();
    }
    Ok(())
}

#[tauri::command]
fn open_kraken_api_page() {
    // Kraken Pro API-key management. The user creates a TRADE-ONLY, NO-withdrawal,
    // IP-whitelisted key here, then pastes it back into the app.
    let _ = open::that("https://pro.kraken.com/app/settings/api");
}

// Upsert `KEY=value` in a list of .env lines.
fn upsert_env(lines: &mut Vec<String>, key: &str, value: &str) {
    let prefix = format!("{key}=");
    for line in lines.iter_mut() {
        if line.starts_with(&prefix) {
            *line = format!("{key}={value}");
            return;
        }
    }
    lines.push(format!("{key}={value}"));
}

#[tauri::command]
fn apply_kraken_key_to_env(app: tauri::AppHandle) -> Result<String, String> {
    let key = kr_entry("kraken_api_key")?
        .get_password()
        .map_err(|_| "No Kraken key saved yet — save one first.".to_string())?;
    let secret = kr_entry("kraken_api_secret")?
        .get_password()
        .map_err(|_| "No Kraken secret saved yet — save one first.".to_string())?;

    let env_path = project_dir(&app).join(".env");
    let existing = std::fs::read_to_string(&env_path).unwrap_or_default();
    let mut lines: Vec<String> = existing.lines().map(|l| l.to_string()).collect();
    upsert_env(&mut lines, "FREQTRADE__EXCHANGE__KEY", &key);
    upsert_env(&mut lines, "FREQTRADE__EXCHANGE__SECRET", &secret);
    std::fs::write(&env_path, lines.join("\n") + "\n").map_err(|e| e.to_string())?;

    Ok("Key written to .env. Restart the stack to load it. Dry-run stays ON — \
        going live is a separate, manual step.".into())
}

#[derive(Serialize)]
struct DockerHealth {
    cli_found: bool,
    daemon_ok: bool,
    compose_file: bool,
    env_exists: bool,
    webui_password: bool,
    ready: bool,
    hint: String,
}

#[tauri::command]
fn docker_health(app: tauri::AppHandle) -> DockerHealth {
    let dir = project_dir(&app);
    let cli = docker_bin();
    let cli_found = cli.is_some();
    let daemon_ok = cli.as_deref().map(docker_daemon_ok).unwrap_or(false);
    let compose_file = dir.join("docker-compose.yml").is_file();
    let env = freqtrade::inspect_env(&dir);
    let (ready, hint) = freqtrade::stack_ready_hint(cli_found, daemon_ok, compose_file, &env);
    DockerHealth {
        cli_found,
        daemon_ok,
        compose_file,
        env_exists: env.env_exists,
        webui_password: env.password_set,
        ready,
        hint,
    }
}

#[tauri::command]
fn copy_env_example(app: tauri::AppHandle) -> Result<String, String> {
    let dir = project_dir(&app);
    let src = dir.join(".env.example");
    let dest = dir.join(".env");
    if dest.exists() {
        return Ok(".env already exists — not overwritten.".into());
    }
    if !src.is_file() {
        return Err("No .env.example in the project folder.".into());
    }
    std::fs::copy(&src, &dest).map_err(|e| e.to_string())?;
    Ok("Copied .env.example → .env. Set FREQTRADE__API_SERVER__PASSWORD, then refresh.".into())
}

#[tauri::command]
fn open_docker_install() {
    let url = if cfg!(target_os = "macos") {
        "https://docs.docker.com/desktop/setup/install/mac-install/"
    } else if cfg!(target_os = "windows") {
        "https://docs.docker.com/desktop/setup/install/windows-install/"
    } else {
        "https://docs.docker.com/engine/install/"
    };
    let _ = open::that(url);
}

#[derive(Serialize)]
struct ConnectionState {
    mode: String,
    remote_origin: String,
    remote_user_saved: bool,
    remote_user_hint: String,
}

#[tauri::command]
fn get_connection(app: tauri::AppHandle) -> ConnectionState {
    let user = kr_entry("remote_webui_user")
        .ok()
        .and_then(|e| e.get_password().ok())
        .unwrap_or_default();
    let hint = if user.len() > 2 {
        format!("{}…", &user[..user.len().min(3)])
    } else if user.is_empty() {
        String::new()
    } else {
        "saved".into()
    };
    ConnectionState {
        mode: connection_mode(&app),
        remote_origin: remote_origin(&app).unwrap_or_default(),
        remote_user_saved: !user.is_empty()
            && kr_entry("remote_webui_password")
                .ok()
                .and_then(|e| e.get_password().ok())
                .is_some_and(|p| !p.is_empty()),
        remote_user_hint: hint,
    }
}

#[tauri::command]
fn set_connection_mode(app: tauri::AppHandle, mode: String) -> Result<(), String> {
    if mode != "local" && mode != "remote" {
        return Err("mode must be local or remote".into());
    }
    write_app_file(&app, "connection_mode.txt", &mode)
}

#[tauri::command]
fn set_remote_origin(app: tauri::AppHandle, origin: String) -> Result<String, String> {
    let origin = freqtrade::normalize_remote_origin(&origin)?;
    write_app_file(&app, "remote_origin.txt", &origin)?;
    Ok(origin)
}

#[tauri::command]
fn save_remote_webui(user: String, password: String) -> Result<(), String> {
    let (user, password) = (user.trim(), password.trim());
    if user.is_empty() || password.is_empty() {
        return Err("Remote WebUI username and password are required.".into());
    }
    kr_entry("remote_webui_user")?
        .set_password(user)
        .map_err(|e| format!("could not save user: {e}"))?;
    kr_entry("remote_webui_password")?
        .set_password(password)
        .map_err(|e| format!("could not save password: {e}"))?;
    Ok(())
}

#[tauri::command]
fn clear_remote_webui() -> Result<(), String> {
    if let Ok(e) = kr_entry("remote_webui_user") {
        let _ = e.delete_password();
    }
    if let Ok(e) = kr_entry("remote_webui_password") {
        let _ = e.delete_password();
    }
    Ok(())
}

#[tauri::command]
fn bot_catalog(app: tauri::AppHandle) -> Result<Vec<freqtrade::BotInfo>, String> {
    fleet_bots(&app)
}

/// JWT-auth to a Freqtrade bot and return P&L + open positions.
/// Local: creds from `.env`. Remote: OS keychain. Never from the webview after save.
#[tauri::command]
fn bot_snapshot(app: tauri::AppHandle, url: String) -> Result<freqtrade::BotSnapshot, String> {
    if is_remote_mode(&app) {
        let (user, pass) = remote_creds()?;
        freqtrade::fetch_snapshot_with_creds(&url, &user, &pass)
    } else {
        freqtrade::fetch_snapshot(&project_dir(&app), &url)
    }
}

#[tauri::command]
fn bot_fleet(app: tauri::AppHandle) -> Result<Vec<freqtrade::FleetEntry>, String> {
    let bots = fleet_bots(&app)?;
    let creds = if is_remote_mode(&app) {
        remote_creds()
    } else {
        let dir = project_dir(&app);
        match std::fs::read_to_string(dir.join(".env")) {
            Ok(text) => freqtrade::parse_env_creds(&text),
            Err(_) => Err("could not read .env — copy .env.example and set the WebUI password".into()),
        }
    };
    Ok(freqtrade::fetch_fleet_from(&bots, &creds))
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .invoke_handler(tauri::generate_handler![
            stack_up,
            stack_down,
            stack_status,
            get_project_dir,
            set_project_dir,
            autostart_enabled,
            set_autostart,
            open_dashboard,
            open_frequi,
            get_connection,
            set_connection_mode,
            set_remote_origin,
            save_remote_webui,
            clear_remote_webui,
            save_kraken_key,
            kraken_key_status,
            clear_kraken_key,
            open_kraken_api_page,
            apply_kraken_key_to_env,
            bot_catalog,
            bot_snapshot,
            bot_fleet,
            docker_health,
            copy_env_example,
            open_docker_install,
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // Tray menu
            let open_i = MenuItem::with_id(app, "open", "Open Dashboard", true, None::<&str>)?;
            let up_i = MenuItem::with_id(app, "up", "Start stack", true, None::<&str>)?;
            let down_i = MenuItem::with_id(app, "down", "Stop stack", true, None::<&str>)?;
            let show_i = MenuItem::with_id(app, "show", "Show window", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_i, &up_i, &down_i, &show_i, &quit_i])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Voltra Controller")
                .menu(&menu)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "open" => open_dashboard(app.clone()),
                    "up" => {
                        let _ = stack_up(app.clone());
                        let _ = app.emit("stack-changed", ());
                    }
                    "down" => {
                        let _ = stack_down(app.clone());
                        let _ = app.emit("stack-changed", ());
                    }
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            // Auto-start the local stack at login only when Docker is ready
            // and we are not in remote-VPS console mode.
            if !is_remote_mode(&handle) {
                let health = docker_health(handle.clone());
                if health.ready {
                    let _ = stack_up(handle);
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Keep running in the tray when the window is closed.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Voltra controller");
}
