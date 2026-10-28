$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
if (-not (Test-Path (Join-Path $Root "data\seed.json"))) {
  Copy-Item (Join-Path $Root "data\seed.example.json") (Join-Path $Root "data\seed.json")
}
if (-not (Test-Path (Join-Path $Root "web\react-dist\index.html"))) {
  throw "前端尚未构建，请先运行 powershell -ExecutionPolicy Bypass -File scripts/setup.ps1"
}
$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { throw "未找到 Python，请先安装并加入 PATH" }
Start-Job -ScriptBlock { Start-Sleep -Seconds 2; Start-Process "http://127.0.0.1:8765/setup" } | Out-Null
& $Python.Source (Join-Path $Root "app.py") --port 8765
