@echo off
cd /d C:\SSe\app\mine-jepa
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot
set PATH=%JAVA_HOME%\bin;%PATH%
uv run python scripts/play_minerl_multi.py --episodes 20
pause
