@echo off
rem Move InProgress\*-output.mp4 to Done\ and empty InProgress\ (deletes the source copies).
python "%~dp0done.py" --dry-run %* || (pause & exit /b 1)
echo.
set /p ok=Proceed? This deletes everything else in InProgress [y/N]: 
if /i "%ok%"=="y" (python "%~dp0done.py" %*) else (echo Cancelled.)
pause
