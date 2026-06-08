@echo off
:: Craft DEMO — isolate the craft loop in MineRLObtainTest-v0 (starts with log=5).
:: Shows the WM v4 + switching planner crafting planks live (chopping set aside).
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

uv run python scripts/play_minerl_multi.py --script scripts/play_craft.py --config configs/play_craft_test.yaml %*
