@echo off
:: Mine-JEPA — wrapper Windows pour uv run
::
:: Pourquoi ce fichier existe :
::   crafter 1.8.3 contient des fichiers UTF-8 que Windows ne peut pas lire
::   avec son codepage par défaut (cp1252). PYTHONUTF8=1 force UTF-8 partout.
::
:: Usage :
::   run.bat scripts/collect.py
::   run.bat scripts/train_encoder.py --epochs 50
::   run.bat scripts/probe.py --label health
::   run.bat -m pytest

set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
uv run python %*
