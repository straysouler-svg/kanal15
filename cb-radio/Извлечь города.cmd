@echo off
chcp 65001 >nul
title CB-рация: распаковка списка городов из игры
set EX=G:\Claude\gruzovichki\tools_untrusted\scs_extractor\scs_extractor.exe
set GAME=G:\SteamLibrary\steamapps\common\Euro Truck Simulator 2
set OUT=G:\Claude\gruzovichki\cb-radio\map\extracted
"%EX%" > "%OUT%_help.txt" 2>&1
echo === def ===
"%EX%" "%GAME%\def.scs" "%OUT%\def"
echo === dlc_east ===
"%EX%" "%GAME%\dlc_east.scs" "%OUT%\dlc_east"
echo === dlc_north ===
"%EX%" "%GAME%\dlc_north.scs" "%OUT%\dlc_north"
echo === dlc_fr ===
"%EX%" "%GAME%\dlc_fr.scs" "%OUT%\dlc_fr"
echo === dlc_it ===
"%EX%" "%GAME%\dlc_it.scs" "%OUT%\dlc_it"
echo === dlc_balt ===
"%EX%" "%GAME%\dlc_balt.scs" "%OUT%\dlc_balt"
echo === dlc_iberia ===
"%EX%" "%GAME%\dlc_iberia.scs" "%OUT%\dlc_iberia"
echo === dlc_balkan_e ===
"%EX%" "%GAME%\dlc_balkan_e.scs" "%OUT%\dlc_balkan_e"
echo === dlc_balkan_w ===
"%EX%" "%GAME%\dlc_balkan_w.scs" "%OUT%\dlc_balkan_w"
echo === dlc_greece ===
"%EX%" "%GAME%\dlc_greece.scs" "%OUT%\dlc_greece"
echo === dlc_polar ===
"%EX%" "%GAME%\dlc_polar.scs" "%OUT%\dlc_polar"
echo.
echo Готово. Напиши Claude: распаковал.
pause
