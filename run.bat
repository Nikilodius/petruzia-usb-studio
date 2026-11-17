@echo off
setlocal
title Petruzia Studio
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

echo [1/2] Checking packages...
%PY% -c "import serial, google.protobuf" >nul 2>nul || (
    echo Installing requirements...
    %PY% -m pip install -r requirements.txt || goto :fail
)

echo [2/2] Starting Petruzia Studio...
pushd petruzia_usb_studio
%PY% app.py
popd
exit /b 0

:fail
echo [ERROR] Failed to install requirements. Check internet connection.
pause
exit /b 1
