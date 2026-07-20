// Voltra desktop controller.
//
// A thin tray app that manages the Dockerized Voltra trading stack — it does
// NOT trade or hold strategy logic itself (that all lives in the Docker
// containers). It just: starts/stops the stack, reports status, opens the
// dashboard, and can enable run-on-login on its own.
//
// SAFETY: this app never sets dry_run=false or touches live-trading config.
// It only runs `docker compose up -d / down / ps` in the project directory.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::Command;

use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_autostart::ManagerExt;

const DEFAULT_PROJECT_DIR: &str = "C:\\Server\\voltra";

// Candidate docker CLI locations (Docker Desktop is often not on PATH).
fn docker_bin() -> String {
    let candidates = [
        "docker",
        "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe",
    ];
    for c in candidates {
        if Command::new(c).arg("--version").output().map(|o| o.status.success()).unwrap_or(false) {
            return c.to_string();
        }
    }
    "docker".to_string()
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
    let dir = project_dir(app);
    let out = Command::new(docker_bin())
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

#[tauri::command]
fn open_dashboard() {
    // Custom dashboard on :8899; falls back silently if the browser call fails.
    let _ = open::that("http://127.0.0.1:8899");
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
                    "open" => open_dashboard(),
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

            // Auto-start the stack when the controller launches at login.
            let _ = stack_up(handle);
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
