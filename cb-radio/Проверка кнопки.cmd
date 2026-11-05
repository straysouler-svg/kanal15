@echo off
chcp 65001 >nul
title CB-рация: проверка кнопки тангенты
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0cb_radio.py" --ptt-test
pause
