@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "EXIT_CODE=0"
set "SKIP_WEB=0"
if /I "%~1"=="--skip-web" set "SKIP_WEB=1"
if /I "%~1"=="/skip-web" set "SKIP_WEB=1"

if "%SKIP_WEB%"=="1" goto skip_web

echo [1/3] Building web frontend - web/dist ...
if not exist "web\package.json" (
  echo ERROR: web\package.json not found.
  set "EXIT_CODE=1"
  goto finish
)
where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm not found. Install Node.js or run: pack_deploy.bat --skip-web
  set "EXIT_CODE=1"
  goto finish
)
pushd web
if not exist node_modules (
  echo Running npm ci...
  call npm ci
  if errorlevel 1 (
    set "EXIT_CODE=1"
    popd
    goto finish
  )
)
call npm run build
if errorlevel 1 (
  echo ERROR: npm run build failed.
  set "EXIT_CODE=1"
  popd
  goto finish
)
if not exist dist\index.html (
  echo ERROR: web\dist\index.html was not created.
  set "EXIT_CODE=1"
  popd
  goto finish
)
popd
echo Web build OK.
goto pack_zip

:skip_web
echo [1/3] Skipping web build - flag --skip-web

:pack_zip
if not "%EXIT_CODE%"=="0" goto finish

echo [2/3] Packing module zip...
if "%SKIP_WEB%"=="1" (
  python scripts\pack_deploy.py
) else (
  python scripts\pack_deploy.py --with-web-dist
)
if errorlevel 1 (
  set "EXIT_CODE=1"
  goto finish
)

echo [3/3] Pack complete.

:finish
echo.
if not "%EXIT_CODE%"=="0" goto failed_summary
echo SUCCESS. Output: dist\kcr-deploy-*.zip
echo Upload and unzip over hoshino/modules/kanna_connection_redive on the server.
echo Included when web was built: web/dist - server does not need npm.
echo NOT included - kept on server: setting_clanbattle.json, data.db, token.json
goto after_summary
:failed_summary
echo FAILED. Exit code: %EXIT_CODE%
:after_summary
echo.
pause
endlocal & exit /b %EXIT_CODE%
