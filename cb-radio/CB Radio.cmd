@echo off
rem Канал 15: рация без окна, значок возле часов (меню: громкость, тишина, журнал, выход)
start "" "G:\Claude\coop-buddy\.venv\Scripts\pythonw.exe" -W ignore "%~dp0cb_radio.py" %*
