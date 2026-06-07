@echo off
:: Phase 4c — Agent MPC world model action-conditioned (eb_jepa) MineRL
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

uv run python scripts/play_minerl_multi.py --script scripts/play_ebwm.py --config configs/play_ebwm.yaml %*
