@echo off
chcp 65001 >nul
title CB-рация: кабины водителей
echo Сначала реплика с фоном кабины, потом только кабина (_bed). Все звуки включены сразу; в игре они выпадают случайно.
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0tools\play_dir.py" "%~dp0samples\cabs"
pause
