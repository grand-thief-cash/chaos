@echo off
setlocal ENABLEDELAYEDEXPANSION

set "script_dir=%~dp0"
for %%I in ("%script_dir%..") do set "work_dir=%%~fI"

echo Working directory is "%work_dir%"
echo.

where go >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo go command not found in PATH. Aborting.
  exit /b 1
)

set "paths=app\infra\go\common app\infra\go\application app\poc\infra\go\application app\poc\infra\go\client app\projects\cronjob app\poc\projects\cronjob"

for %%P in (%paths%) do call :process "%%P"
exit /b 0

:run
REM %* is the command to run
echo   ^> %*
%*
if ERRORLEVEL 1 (
  echo   !! command failed: %*
  exit /b 1
)
exit /b 0

:process
set "rel=%~1"
set "full_path=%work_dir%\%rel%"
echo Processing directory: "%full_path%"

if exist "%full_path%" (
  pushd "%full_path%" >NUL

  call :run go mod tidy || (
    echo.
    popd
    goto :eof
  )

  call :run go mod vendor || (
    echo.
    popd
    goto :eof
  )

  popd
) else (
  echo   !! Directory "%full_path%" does not exist, skipping.
)
echo.
goto :eof