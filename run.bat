@echo off
:: Mine-JEPA — Windows wrapper for uv run
::
:: Why this file exists:
::   crafter 1.8.3 contains UTF-8 files that Windows cannot read
::   with its default codepage (cp1252). PYTHONUTF8=1 forces UTF-8 everywhere.
::
:: Usage:
::   run.bat scripts/collect.py
::   run.bat scripts/train_encoder.py --epochs 50
::   run.bat scripts/probe.py --label health
::   run.bat -m pytest

set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot
set PATH=%JAVA_HOME%\bin;%PATH%
uv run python %*
