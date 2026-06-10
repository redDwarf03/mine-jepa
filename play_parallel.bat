@echo off
:: Parallel JEPA agents — N single-agent Minecraft worlds at once, stitched side by side.
:: Usage: play_parallel.bat            (2 agents, Treechop eb-JEPA)
::        play_parallel.bat --agents 2
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot"
set PATH=%JAVA_HOME%\bin;%PATH%

uv run python scripts/play_parallel.py %*
