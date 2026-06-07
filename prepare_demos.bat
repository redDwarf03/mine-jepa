@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ============================================================
echo Preparing MineRL demos (frames + rewards + actions)
echo 210 demos, ~20 min depending on disk speed
echo ============================================================

uv run python scripts/prepare_demos.py ^
    --data data\MineRL_demos\MineRLTreechop-v0 ^
    --out data\minerl_goal

pause
