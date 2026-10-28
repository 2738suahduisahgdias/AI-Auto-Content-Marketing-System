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
if ($Check) {
  & $Python.Source --version
  node --version
  ffmpeg -version | Select-Object -First 1
  Write-Host "核心命令检查通过。"
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
Write-Host "安装完成。启动：powershell -ExecutionPolicy Bypass -File scripts/start.ps1"
Write-Host "访问：http://127.0.0.1:8765/"
