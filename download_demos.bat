@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

echo ============================================================
echo Downloading MineRLTreechop-v0 demos (Zenodo, 1.5 GB)
echo ============================================================

:: Create destination folder
if not exist data\MineRL_demos mkdir data\MineRL_demos

:: Download with curl (available on Windows 10+)
echo Starting download...
curl -L --progress-bar -o data\MineRL_demos\MineRLTreechop-v0.zip "https://zenodo.org/records/12659939/files/MineRLTreechop-v0.zip?download=1"

if %ERRORLEVEL% neq 0 (
    echo ERROR downloading
    pause
    exit /b 1
)

echo.
echo Download OK. Extracting...
powershell -Command "Expand-Archive -Path 'data\MineRL_demos\MineRLTreechop-v0.zip' -DestinationPath 'data\MineRL_demos\MineRLTreechop-v0' -Force"

if %ERRORLEVEL% neq 0 (
    echo ERROR extracting
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Dataset extracted to data\MineRL_demos\MineRLTreechop-v0\
echo Launching data preparation...
echo ============================================================

uv run python scripts/prepare_demos.py --data data\MineRL_demos\MineRLTreechop-v0 --out data\minerl_goal

pause
