param([switch]$Check)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Missing = @()
foreach ($Name in @("node", "npm", "ffmpeg", "ffprobe")) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { $Missing += $Name }
}
$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { $Missing += "Python" }
$ChromePaths = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
if (-not ($ChromePaths | Where-Object { Test-Path $_ })) { $Missing += "Chrome" }
if ($Missing.Count -gt 0) {
  Write-Error "缺少核心依赖：$($Missing -join '、')。请先安装并加入 PATH，然后重新运行本脚本。"
  exit 1
}
function Test-WebBridge {
  try {
    $Status = Invoke-RestMethod -Uri "http://127.0.0.1:10086/status" -TimeoutSec 3
    $Daemon = if ($Status.running) { "已运行" } else { "未运行" }
    $Extension = if ($Status.extension_connected) { "已连接" } else { "未连接" }
    Write-Host "WebBridge 服务：$Daemon；Chrome 扩展：$Extension"
    if (-not $Status.extension_connected) { Write-Host "请在 Chrome 安装并启用 Kimi WebBridge 扩展，再重新检查。" }
  } catch {
    Write-Host "WebBridge 未连接：平台采集和微信发布前，请先安装并启动它。"
    Write-Host "安装：https://www.kimi.com/zh-cn/features/webbridge"
    Write-Host "启动：& `"$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe`" start"
  }
}
if ($Check) {
  & $Python.Source --version
  node --version
  ffmpeg -version | Select-Object -First 1
  Write-Host "核心命令检查通过。"
  Test-WebBridge
  exit 0
}

$VenvPython = Join-Path $Root ".venv-topics\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  & $Python.Source -m venv (Join-Path $Root ".venv-topics")
  if ($LASTEXITCODE -ne 0) { throw "创建隔离环境失败" }
}
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements-topics.txt")
if ($LASTEXITCODE -ne 0) { throw "采集依赖安装失败" }
Set-Location (Join-Path $Root "webapp")
npm ci
if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
Set-Location (Join-Path $Root "remotion-app")
npm ci
if ($LASTEXITCODE -ne 0) { throw "Remotion 依赖安装失败" }
Set-Location $Root
if (-not (Test-Path (Join-Path $Root "data\seed.json"))) {
  Copy-Item (Join-Path $Root "data\seed.example.json") (Join-Path $Root "data\seed.json")
}
Test-WebBridge
Write-Host "安装完成。启动：powershell -ExecutionPolicy Bypass -File scripts/start.ps1"
Write-Host "访问：http://127.0.0.1:8765/"
