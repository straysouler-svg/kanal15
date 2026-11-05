@echo off
chcp 65001 >nul
title CB-рация: голоса OpenRouter (анекдот Михалыча)
echo gpt-audio-mini: ash, ballad, cedar, echo, onyx, verse; gpt-audio: ash (дороже в 25 раз)
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0tools\play_dir.py" "%~dp0samples\openrouter"
pause
