@echo off
chcp 65001 >nul
rem «Онлайн-конвой», этап 1 — живая приёмка после стрима (см. prompts/guest_sync_task_2026-11-12.md).
rem Поднимает обе рации на одном ПК: хозяин (принимает гостя) + гость (тонкий клиент).
rem НЕ запускать во время стрима: обе рации играют звук и читают телеметрию.
set ROOT=%~dp0..\..
set PY=%ROOT%\build\venv\Scripts\python.exe

echo Собираю папку гостя...
"%PY%" "%ROOT%\cb-radio\tools\make_guest.py" || exit /b 1

echo.
echo Хозяин (эфир как обычно + приём гостя) — отдельное окно.
start "Канал 15 — хозяин" "%PY%" "%ROOT%\cb-radio\cb_radio.py" --console --guest-host

timeout /t 3 >nul

echo Гость (слышит эфир хозяина) — отдельное окно.
start "Канал 15 — гость" "%PY%" "%ROOT%\build\_guest\cb_radio.py" --guest 127.0.0.1:47821

echo.
echo Оба окна подняты. Проверка по постановке:
echo  1. поездка ~20 минут: число play у хозяина = числу реплик у гостя (пропуски — в его журнале);
echo  2. тангента F9 в окне гостя и тангента руля у хозяина обрывают эфир у обоих;
echo  3. фраза гостя: напишите текст в build\_guest\guest_say.txt — водитель ответит;
echo  4. после теста: сравнить хэши основной папки с build\_guest\before_hashes.txt.
pause
