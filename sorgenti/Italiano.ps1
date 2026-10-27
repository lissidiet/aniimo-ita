# Aniimo in italiano: controlla la patch e la aggiorna se serve.
# Si avvia da solo come amministratore. Opzioni: -Controlla (non cambia niente), -Ripristina.
param([switch]$Controlla, [switch]$Ripristina)

$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin -and -not $Controlla) {
    $extra = if ($Ripristina) { "-Ripristina" } else { "" }
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" $extra"
    exit
}

$host.UI.RawUI.WindowTitle = "Aniimo in italiano"
$python = Join-Path $qui ".venv\Scripts\python.exe"
$opzioni = @()
if ($Controlla) { $opzioni += "--controlla" }
if ($Ripristina) { $opzioni += "--ripristina" }

Push-Location $qui
& $python aggiorna.py @opzioni
Pop-Location

Write-Host ""
Read-Host "Premi Invio per chiudere"
