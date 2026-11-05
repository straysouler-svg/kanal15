@echo off
chcp 65001 >nul
title CB-рация: gpt-audio со смехом
echo Борода (onyx), Михалыч (ash), Стас (verse): сначала чистый голос (dry), потом через рацию (radio)
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0tools\play_dir.py" "%~dp0samples\openrouter_full"
pause
