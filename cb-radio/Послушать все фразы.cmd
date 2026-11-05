@echo off
chcp 65001 >nul
title CB-рация: прослушка
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0cb_radio.py" --listen
pause
