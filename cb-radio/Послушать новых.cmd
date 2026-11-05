@echo off
chcp 65001 >nul
title CB-рация: новые персонажи
echo Студент, Профессор, Петровна, Тень, Витёк (фразы и сценки)
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0cb_radio.py" --listen student professor petrovna ten vitek
pause
