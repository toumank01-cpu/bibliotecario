@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==============================================
echo   BIBLIOTECARIO - CONEXION CON TU PC
 echo ==============================================

echo.
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No encuentro cloudflared en el PATH.
  echo Instala cloudflared y vuelve a ejecutar este archivo.
  echo Documentacion oficial: https://developers.cloudflare.com/tunnel/downloads/
  pause
  exit /b 1
)

if not exist ".api-key" (
  powershell -NoProfile -Command "$k=[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N');Set-Content -NoNewline -Encoding ascii '.api-key' $k"
)
set /p BIBLIOTECARIO_API_KEY=<.api-key
if "%BIBLIOTECARIO_API_KEY%"=="" (
  echo [ERROR] No se pudo crear la clave API.
  pause
  exit /b 1
)

echo.
echo [OK] Clave API local preparada.
echo [INFO] No publiques ni compartas el archivo .api-key.
echo.
echo [1/2] Iniciando backend FastAPI en 127.0.0.1:8000...
start "Bibliotecario API" cmd /k "cd /d "%~dp0" && set BIBLIOTECARIO_API_KEY=%BIBLIOTECARIO_API_KEY% && call run.bat"

timeout /t 4 /nobreak >nul

echo [2/2] Abriendo tunel HTTPS temporal de Cloudflare...
echo.
echo Cuando aparezca una URL https://...trycloudflare.com, esa sera la URL publica de la API.
echo Introducela en la pagina de Bibliotecario junto con la clave del archivo .api-key.
echo.
cloudflared tunnel --url http://127.0.0.1:8000

endlocal
