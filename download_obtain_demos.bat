@echo off
:: Download MineRLObtainIronPickaxe-v0 human demos (Zenodo, 2.8 GB)
:: These demos show the FULL tech tree: log -> planks -> stick -> crafting_table
:: -> wooden_pickaxe -> ... -> iron_pickaxe. Used to bootstrap the world model
:: for the crafting milestones (Phase 5: craft a wooden tool).
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ============================================================
echo Downloading MineRLObtainIronPickaxe-v0 demos (Zenodo, 2.8 GB)
echo ============================================================

if not exist data\MineRL_demos mkdir data\MineRL_demos

echo Starting download...
curl -L --progress-bar -o data\MineRL_demos\MineRLObtainIronPickaxe-v0.zip "https://zenodo.org/records/12659939/files/MineRLObtainIronPickaxe-v0.zip?download=1"

if %ERRORLEVEL% neq 0 (
    echo ERROR downloading
    pause
    exit /b 1
)

echo.
echo Download OK. Extracting...
powershell -Command "Expand-Archive -Path 'data\MineRL_demos\MineRLObtainIronPickaxe-v0.zip' -DestinationPath 'data\MineRL_demos\MineRLObtainIronPickaxe-v0' -Force"

if %ERRORLEVEL% neq 0 (
    echo ERROR extracting
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Dataset extracted to data\MineRL_demos\MineRLObtainIronPickaxe-v0\
echo Next: run.bat scripts/prepare_demos_obtain.py
echo ============================================================
pause
