@echo off
REM ======================================================
REM run_poc.bat - Build & run grpc server and client (POC)
REM Repo root expected (folder containing app\infra and app\poc)
REM ======================================================

setlocal ENABLEDELAYEDEXPANSION

REM -------- Configuration --------
set CONFIG=app\poc\infra\go\client\config\config.yaml
set ENV=dev
set SERVER_DIR=app\poc\infra\go\application
set CLIENT_DIR=app\poc\infra\go\client
set LOG_DIR=logs
set SERVER_LOG=%LOG_DIR%\server.out.log
set CLIENT_LOG=%LOG_DIR%\client.out.log

REM -------- Checks --------
if not exist "%CONFIG%" (
  echo [ERROR] Config file not found: %CONFIG%
  exit /b 1
)

for /f "tokens=2 delims==" %%v in ('go version 2^>NUL') do (
  REM just triggering error if go missing
)
if errorlevel 1 (
  echo [ERROR] Go toolchain not found in PATH.
  exit /b 1
)

REM -------- Prepare logs --------
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [INFO] Starting gRPC server...
pushd "%SERVER_DIR%"
start "grpc_server" cmd /c go run . "%CONFIG%" "%ENV%" ^> "..\..\..\..\..\%SERVER_LOG%" 2^>^&1
if errorlevel 1 (
  echo [ERROR] Failed to launch server.
  popd
  exit /b 1
)
popd

REM Wait a moment for server to bind
echo [INFO] Waiting for server to initialize...
timeout /t 3 /nobreak >NUL

echo [INFO] Running gRPC client single-shot hook call...
pushd "%CLIENT_DIR%"
go run . "%CONFIG%" "%ENV%" ^> "..\..\..\..\..\%CLIENT_LOG%" 2^>^&1
set CLIENT_RC=%ERRORLEVEL%
popd

if %CLIENT_RC% NEQ 0 (
  echo [WARN] Client exited with error code %CLIENT_RC%. Check %CLIENT_LOG%
) else (
  echo [INFO] Client completed successfully.
)

echo.
echo [INFO] Tail (last 15 lines) of client log:
powershell -NoLogo -NoProfile -Command ^
  "Get-Content -Path '%CLIENT_LOG%' -Tail 15 | ForEach-Object { Write-Host $_ }"

echo.
echo [INFO] Server is still running (launched in separate window).
echo [INFO] To stop it, close the 'grpc_server' window or use taskkill:
echo        taskkill /FI "WINDOWTITLE eq grpc_server*" /T /F
echo.
echo [DONE]

endlocal
exit /b 0