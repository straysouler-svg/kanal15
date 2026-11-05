@echo off
chcp 65001 >nul
title Канал 15 — сборка установщиков
cd /d "%~dp0"
echo Собираю установщики «Канала 15» (версия в version.json). Это займёт 10-15 минут, окно можно свернуть.
echo.
set PYTHONIOENCODING=utf-8
set OR_BUDGET=1.0
set VPY=G:\Claude\coop-buddy\.venv\Scripts\python.exe
set BPY=G:\Claude\gruzovichki\build\venv\Scripts\python.exe
echo [1/5] Варианты обращений (Кирилл / общая), озвучиваются только новые...
"%VPY%" tools\gen_variants.py kirill || goto :err
"%VPY%" tools\gen_variants.py neutral || goto :err
echo [2/5] Проверка эфира...
"%VPY%" tools\check_air.py || goto :err
echo [3/5] Упаковка...
"%VPY%" tools\pack_release.py kirill || goto :err
"%VPY%" tools\pack_release.py neutral || goto :err
echo [4/5] Установщик для Кирилла...
"%BPY%" tools\build_exe.py kirill || goto :err
echo [5/5] Общий установщик...
"%BPY%" tools\build_exe.py neutral || goto :err
echo.
echo ГОТОВО. Установщики лежат в G:\Claude\gruzovichki\release
explorer "G:\Claude\gruzovichki\release"
pause
exit /b 0
:err
echo.
echo ОШИБКА на этом шаге — пришли Claude скриншот этого окна.
pause
exit /b 1
