<#
  install_agent.ps1 — register the RMM agent to start for ANY user who logs in.

  Multi-user design: the agent must run inside the logged-in person's desktop
  so its tray icon and session notification are visible. A SYSTEM service can't
  show UI, so we use a Scheduled Task that triggers at logon of any user and
  runs in that user's session.

  Run from an elevated PowerShell (Administrator):
    .\install_agent.ps1 -ServerUrl "wss://156.67.25.167:8765" -Token "<machine-token>" `
        -ExePath "C:\Program Files\RMMAgent\rmm-agent.exe"
#>
param(
    [Parameter(Mandatory = $true)] [string] $ServerUrl,
    [Parameter(Mandatory = $true)] [string] $Token,
    [string] $ExePath = "C:\Program Files\RMMAgent\rmm-agent.exe",
    [ValidateSet("Limited", "Highest")] [string] $RunLevel = "Limited"
)

$ErrorActionPreference = "Stop"
$TaskName = "RMM Agent"
$DataDir  = Join-Path $env:ProgramData "RMAgent"

Write-Host "Installing RMM agent (multi-user logon task)..."

# 1) Machine-wide data dir for the shared config + single-instance lock.
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
icacls $DataDir /grant "*S-1-5-32-545:(OI)(CI)M" | Out-Null   # Users = Modify

# 2) Shared config.json (one machine token for the whole PC).
$config = [ordered]@{
    server_url         = $ServerUrl
    token              = $Token
    show_tray_icon     = $true
    notify_on_session  = $true
    allow_remote_input = $true
} | ConvertTo-Json
Set-Content -Path (Join-Path $DataDir "config.json") -Value $config -Encoding UTF8

if (-not (Test-Path $ExePath)) {
    Write-Warning "Agent exe not found at $ExePath. Copy your PyInstaller build there before logon."
}

# 3) Scheduled Task: trigger at logon of ANY user, run in that user's session.
$action    = New-ScheduledTaskAction -Execute $ExePath
$trigger   = New-ScheduledTaskTrigger -AtLogOn                  # any user (no -User)
$principal = New-ScheduledTaskPrincipal -GroupId "S-1-5-32-545" -RunLevel $RunLevel
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Done. '$TaskName' will start for each user at logon."
Write-Host "Note: RunLevel=$RunLevel. Use -RunLevel Highest only if you must control"
Write-Host "      UAC/elevated windows; Limited is the safer default."