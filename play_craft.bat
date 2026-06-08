@echo off
:: Craft milestone — WM v4 agent in MineRLObtainIronPickaxeDense (chop log -> craft planks)
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

uv run python scripts/play_minerl_multi.py --script scripts/play_craft.py --config configs/play_craft.yaml %*
