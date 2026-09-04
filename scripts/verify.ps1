# Verificación completa del backend (Windows / PowerShell)
# Uso:  .\scripts\verify.ps1
# Requiere: Docker corriendo + Node (para newman). Levanta la pila si hace falta
# y ejecuta los 37 requests de la colección Postman contra la API en Docker.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> 1/3  Asegurando que la pila Docker esté arriba..." -ForegroundColor Cyan
docker compose up -d --build | Out-Null

Write-Host "==> 2/3  Esperando a que la API responda /health..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 3
        if ($r.status -eq "ok") { $ok = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ok) { Write-Error "La API no respondió a tiempo. Revisa: docker compose logs api"; exit 1 }
Write-Host "    API lista." -ForegroundColor Green

Write-Host "==> 3/3  Ejecutando colección Postman (newman)..." -ForegroundColor Cyan
npx newman run postman/Serial_Manager.postman_collection.json `
    -e postman/Serial_Manager.local.postman_environment.json `
    -r cli,htmlextra `
    --reporter-htmlextra-export reports/newman-report.html `
    --reporter-htmlextra-title "Serial Manager - Verificacion Backend"

Write-Host ""
Write-Host "Reporte HTML: reports\newman-report.html" -ForegroundColor Green
