$ErrorActionPreference = "Stop"

Write-Host "[1/3] Installing/Upgrading PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pyinstaller

Write-Host "[2/3] Building adb_toolbox_gui.exe ..." -ForegroundColor Cyan
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  "adb_toolbox_gui.py"

Write-Host "[3/3] Done." -ForegroundColor Green
Write-Host "Output: .\dist\adb_toolbox_gui.exe" -ForegroundColor Yellow
