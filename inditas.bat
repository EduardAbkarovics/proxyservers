@echo off
cd /d %~dp0

if not exist venv (
    echo Virtualis kornyezet letrehozasa...
    python -m venv venv
)

echo Konyvtarak telepitese...
venv\Scripts\pip install -q requests

echo Proxy server indul...
venv\Scripts\python proxy_rotator.py
pause
