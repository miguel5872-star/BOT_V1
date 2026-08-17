@echo off
chcp 65001 >nul
title Bot de papel - solo consultar
cd /d "%~dp0"
python bot.py report
python grafica.py
start "" "%~dp0index.html"
pause
