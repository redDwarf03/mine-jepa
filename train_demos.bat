@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

echo ============================================================
echo STEP 1/2: JEPA encoder on human demos (453k frames)
echo ============================================================
uv run python scripts/train_encoder.py --config configs/train_encoder_demos.yaml

if %ERRORLEVEL% neq 0 (
    echo ERROR encoder
    pause
    exit /b 1
)

echo.
echo ============================================================
echo STEP 2/2: World Model on human demos
echo ============================================================
uv run python scripts/train_wm.py --config configs/train_wm_demos.yaml

if %ERRORLEVEL% neq 0 (
    echo ERROR world model
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Training complete!
echo  encoder_demos.pt  + wm_demos.pt in checkpoints/
echo Next step: update play_minerl.yaml and re-run
echo ============================================================
pause
