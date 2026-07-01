<#
  uninstall_agent.ps1 — remove the RMM agent logon task and its data.
  Run from an elevated PowerShell (Administrator).
#>
$ErrorActionPreference = "SilentlyContinue"
$TaskName = "RMM Agent"
$DataDir  = Join-Path $env:ProgramData "RMAgent"

Write-Host "Removing '$TaskName'..."
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Removing data dir $DataDir..."
Remove-Item -Recurse -Force -Path $DataDir

Write-Host "Done. (Running agent processes exit on next logoff; reboot to be sure.)"