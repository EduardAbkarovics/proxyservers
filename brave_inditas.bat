@echo off
cd /d %~dp0

if not exist venv (
    echo Virtualis kornyezet letrehozasa...
    python -m venv venv
    venv\Scripts\pip install -q requests
)

echo Proxy server indul...
start "ProxyRotator - IP Valtozo" venv\Scripts\python proxy_rotator.py

echo Varakozas amig a proxy elindul...
timeout /t 3 /nobreak >nul

echo Brave bezarasa ha fut...
taskkill /f /im brave.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Brave indul proxy-val...
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --proxy-server="http://127.0.0.1:8080"

echo Kesz! Nezd a "ProxyRotator - IP Valtozo" ablakot az IP valtozasokhoz.
