@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LOG=papel\ciclos.log
set PY=C:\Users\user\anaconda3\python.exe

echo. >> "%LOG%"
echo ================ %DATE% %TIME% ================ >> "%LOG%"

"%PY%" bot.py step >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] fallo el ciclo >> "%LOG%"
  exit /b 1
)

"%PY%" bot.py readme  >> "%LOG%" 2>&1
"%PY%" grafica.py     >> "%LOG%" 2>&1

git add papel/ README.md index.html >> "%LOG%" 2>&1
git diff --staged --quiet
if errorlevel 1 (
  git commit -m "paso local %DATE% %TIME%" >> "%LOG%" 2>&1
  git push origin main >> "%LOG%" 2>&1
  if errorlevel 1 echo [AVISO] no se pudo subir a GitHub, el estado local si se guardo >> "%LOG%"
)
exit /b 0
