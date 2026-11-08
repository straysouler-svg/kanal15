@echo off
chcp 65001 >nul
title Канал 15: остатки на ключах
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0tools\check_quota.py"
pause
