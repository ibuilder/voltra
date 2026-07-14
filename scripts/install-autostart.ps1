# Installs SolSignal autostart (run once, no admin needed):
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
# - copies start-solsignal.cmd into the current user's Startup folder so the
#   stack comes up at every login
# - disables sleep/hibernate on AC power so the machine stays available
# Undo: delete the Startup shortcut (see path printed below) and
#       powercfg /change standby-timeout-ac 30

$ErrorActionPreference = "Stop"
$proj    = "C:\Server\solsignal"
$launcher = Join-Path $proj "scripts\start-solsignal.cmd"
$startup = [Environment]::GetFolderPath("Startup")
$dest    = Join-Path $startup "SolSignal.cmd"

Copy-Item -Path $launcher -Destination $dest -Force
Write-Host "Installed autostart -> $dest"

# Keep the machine awake on AC power (the #1 dry-run risk was sleep/reboot)
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
Write-Host "Disabled AC sleep/hibernate."

Write-Host ""
Write-Host "Done. The stack will auto-start at your next login."
Write-Host "To undo: delete '$dest' and run 'powercfg /change standby-timeout-ac 30'."
