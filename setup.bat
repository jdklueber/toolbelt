@echo off
setlocal

echo === toolbelt setup for Windows ===
echo.

:: Check for uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo uv not found. Installing via winget...
    winget install --id astral-sh.uv -e --silent
    :: winget can return non-zero for "reboot required" or dependency side-effects
    :: even when the install succeeded. Check for the binary directly instead.
    if exist "%LOCALAPPDATA%\Programs\uv\uv.exe" (
        echo uv installed. You may need to restart your terminal for PATH to update.
    ) else (
        where uv >nul 2>&1
        if %errorlevel% neq 0 (
            echo.
            echo winget install failed. Install uv manually:
            echo   https://docs.astral.sh/uv/getting-started/installation/
            exit /b 1
        )
        echo uv installed.
    )
) else (
    echo uv is already installed.
)

echo.
echo Setup complete. Next steps:
echo.
echo   1. Add this directory to PATH (System Properties ^> Environment Variables):
echo      %~dp0
echo.
echo   2. Set TOOLBELT_CONFIG to your config/secrets directory (e.g. D:\etc)
echo      (also in System Properties ^> Environment Variables)
echo.
echo   3. Open a new terminal and run:  toolbelt hello

endlocal
