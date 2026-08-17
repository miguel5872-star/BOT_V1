@echo off
chcp 65001 >nul
title Bot de papel - momentum de funding
cd /d "%~dp0"

echo.
echo  ============================================================
echo   BOT DE PAPEL - MOMENTUM DE FUNDING
echo  ============================================================
echo.
echo  [1/3] Ejecutando un ciclo (marcar a mercado, cerrar/abrir tramos)...
echo.
python bot.py step
if errorlevel 1 (
  echo.
  echo  ERROR al ejecutar el ciclo. Revisa la conexion a internet.
  echo.
  pause
  exit /b 1
)

echo.
echo  [2/3] Resumen del historial
echo.
python bot.py report

echo.
echo  [3/3] Generando el panel...
python grafica.py
start "" "%~dp0index.html"

echo.
echo  Listo. El panel se ha abierto en tu navegador.
echo.
pause
