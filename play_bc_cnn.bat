@echo off
:: Phase 4b — Agent BC CNN end-to-end MineRL
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

uv run python scripts/play_minerl_multi.py --config configs/play_bc_cnn.yaml %*
