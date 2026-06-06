@echo off
:: FTMO R2 sync + journal review
:: Runs on the Windows host before the Cowork reviewer fires (08:45 SGT daily).
:: Writes synced data to C:\ftmo-sync and a dated report to C:\ftmo-sync\reports\.

setlocal
set PROJ=D:\Software Development\thetradingbotofcc-forex
set DEST=C:\ftmo-sync
set LOG=C:\ftmo-sync\sync_log.txt

cd /d "%PROJ%"

echo [%date% %time%] Starting R2 sync >> "%LOG%" 2>&1
py scripts\sync_r2.py pull --prefix vps --dest "%DEST%" >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%date% %time%] sync_r2.py failed with exit code %ERRORLEVEL% >> "%LOG%" 2>&1
    exit /b %ERRORLEVEL%
)

echo [%date% %time%] Running journal review >> "%LOG%" 2>&1
py scripts\review_journal.py --state "%DEST%" >> "%LOG%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%date% %time%] review_journal.py failed with exit code %ERRORLEVEL% >> "%LOG%" 2>&1
    exit /b %ERRORLEVEL%
)

echo [%date% %time%] Done >> "%LOG%" 2>&1
endlocal
