@echo off
chcp 65001 >nul
title CB-рация: фон кабины до/после
echo Пары: A_old = без фона, C_street = дорога, ветер из окна, трафик, гудки (Михалыч, Борода, Ласточка, Стас, Янек)
"G:\Claude\coop-buddy\.venv\Scripts\python.exe" -W ignore "%~dp0tools\play_dir.py" "%~dp0samples\cab_test"
pause