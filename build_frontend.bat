@echo off
setlocal enabledelayedexpansion

:: Colors
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "RESET=[0m"

echo.
echo %CYAN%===============================
echo   Building Electron Frontend
echo ===============================%RESET%
echo.

cd /d %~dp0
cd gui

:: Check if directory exists
if not exist "package.json" (
    echo %RED%[ERROR]%RESET% package.json not found! Are you in the correct directory?
    exit /b 1
)

:: Check Node.js
echo %YELLOW%[INFO]%RESET% Checking Node.js installation...
node --version >nul 2>&1
if !errorlevel! neq 0 (
    echo %RED%[ERROR]%RESET% Node.js not found! Please install Node.js first
    exit /b 1
)
echo %GREEN%[OK]%RESET% Node.js version:
node --version

:: Check npm
echo.
echo %YELLOW%[INFO]%RESET% Checking npm installation...
npm --version >nul 2>&1
if !errorlevel! neq 0 (
    echo %RED%[ERROR]%RESET% npm not found!
    exit /b 1
)
echo %GREEN%[OK]%RESET% npm version:
npm --version

:: Check node_modules
echo.
if not exist "node_modules" (
    echo %YELLOW%[WARN]%RESET% node_modules not found, installing dependencies...
    echo %YELLOW%[INFO]%RESET% Running: npm install
    npm install
    if !errorlevel! neq 0 (
        echo %RED%[ERROR]%RESET% Failed to install dependencies
        exit /b 1
    )
    echo %GREEN%[OK]%RESET% Dependencies installed
) else (
    echo %GREEN%[OK]%RESET% node_modules found
)

:: Check build script
echo.
echo %YELLOW%[INFO]%RESET% Checking build configuration...
findstr /C:"build:win" package.json >nul 2>&1
if !errorlevel! neq 0 (
    echo %RED%[ERROR]%RESET% build:win script not found in package.json
    exit /b 1
)
echo %GREEN%[OK]%RESET% Build script configured

:: Clean previous build
echo.
echo %YELLOW%[INFO]%RESET% Cleaning previous build artifacts...
if exist "dist" (
    rmdir /s /q "dist"
    echo %GREEN%[OK]%RESET% Cleaned dist folder
)
if exist "release" (
    rmdir /s /q "release"
    echo %GREEN%[OK]%RESET% Cleaned release folder
)

:: Build Electron app
echo.
echo %BLUE%========================================
echo   Building Electron Application
echo ========================================%RESET%
echo.
echo %YELLOW%[INFO]%RESET% This may take a few minutes...
echo.

npm run build:win

if !errorlevel! neq 0 (
    echo.
    echo %RED%[ERROR]%RESET% Electron build failed!
    echo %YELLOW%[INFO]%RESET% Check the error messages above
    exit /b 1
)

:: Verify build output
echo.
echo %YELLOW%[INFO]%RESET% Verifying build output...

set "BUILD_FOUND=0"
if exist "dist\*.exe" set "BUILD_FOUND=1"
if exist "release\*.exe" set "BUILD_FOUND=1"
if exist "out\*.exe" set "BUILD_FOUND=1"

if !BUILD_FOUND! equ 0 (
    echo %RED%[ERROR]%RESET% Build output not found!
    echo %YELLOW%[INFO]%RESET% Expected .exe file in dist, release, or out folder
    exit /b 1
)

:: Display build artifacts
echo %GREEN%[OK]%RESET% Build artifacts created:
echo.
if exist "dist\*.exe" (
    for %%F in (dist\*.exe) do (
        set "file=%%F"
        for %%A in ("!file!") do set size=%%~zA
        set /a size_mb=!size! / 1048576
        echo   %CYAN%- %%~nxF%RESET% (!size_mb! MB)
    )
)
if exist "release\*.exe" (
    for %%F in (release\*.exe) do (
        set "file=%%F"
        for %%A in ("!file!") do set size=%%~zA
        set /a size_mb=!size! / 1048576
        echo   %CYAN%- %%~nxF%RESET% (!size_mb! MB)
    )
)

:: Build summary
echo.
echo %GREEN%========================================
echo   Frontend Build Completed Successfully
echo ========================================%RESET%
echo.
echo %GREEN%[SUCCESS]%RESET% Electron application built
echo %GREEN%[SUCCESS]%RESET% Ready for distribution
echo.

exit /b 0