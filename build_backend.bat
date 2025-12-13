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
echo   Building Python Backend
echo ===============================%RESET%
echo.

cd /d %~dp0
cd windows-listener

:: Check if directory exists
if not exist "windows-listener" (
    if not exist "main.py" (
        echo %RED%[ERROR]%RESET% windows-listener directory not found!
        exit /b 1
    )
)

:: Check virtual environment
echo %YELLOW%[INFO]%RESET% Checking virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo %RED%[ERROR]%RESET% Virtual environment not found at .venv
    echo %YELLOW%[INFO]%RESET% Please create venv first: python -m venv .venv
    exit /b 1
)

:: Activate virtual environment
echo %YELLOW%[INFO]%RESET% Activating virtual environment...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo %RED%[ERROR]%RESET% Failed to activate virtual environment
    exit /b 1
)
echo %GREEN%[OK]%RESET% Virtual environment activated

:: Check Python version
echo.
echo %YELLOW%[INFO]%RESET% Python version:
python --version
echo.

:: Install dependencies
echo %YELLOW%[INFO]%RESET% Installing dependencies...
if not exist "requirements.txt" (
    echo %RED%[ERROR]%RESET% requirements.txt not found!
    exit /b 1
)

pip install -r requirements.txt --quiet --disable-pip-version-check
if !errorlevel! neq 0 (
    echo %RED%[ERROR]%RESET% Failed to install dependencies
    exit /b 1
)
echo %GREEN%[OK]%RESET% Dependencies installed

:: Check PyInstaller
echo.
echo %YELLOW%[INFO]%RESET% Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo %YELLOW%[WARN]%RESET% PyInstaller not found, installing...
    pip install pyinstaller
)
echo %GREEN%[OK]%RESET% PyInstaller ready

:: Clean previous build
echo.
echo %YELLOW%[INFO]%RESET% Cleaning previous build artifacts...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"
echo %GREEN%[OK]%RESET% Cleaned

:: Build with PyInstaller
echo.
echo %BLUE%========================================
echo   Building executable with PyInstaller
echo ========================================%RESET%
echo.

:: Prepare PyInstaller command
set "PY_CMD=pyinstaller --clean --onefile --noconsole --name ble_bridge"

:: Add icon if exists
if exist "icon.ico" (
    echo %YELLOW%[INFO]%RESET% Adding icon: icon.ico
    set "PY_CMD=!PY_CMD! --icon=icon.ico"
)

:: Add config folder if exists
if exist "config" (
    echo %YELLOW%[INFO]%RESET% Adding config folder
    set "PY_CMD=!PY_CMD! --add-data config;config"
)

:: Add hidden imports
set "PY_CMD=!PY_CMD! --hidden-import=asyncio --hidden-import=bleak"

:: Add main.py
set "PY_CMD=!PY_CMD! main.py"

echo %YELLOW%[INFO]%RESET% Running PyInstaller...
echo.
%PY_CMD%

if !errorlevel! neq 0 (
    echo.
    echo %RED%[ERROR]%RESET% PyInstaller build failed!
    echo %YELLOW%[INFO]%RESET% Check the error messages above
    exit /b 1
)

:: Verify build output
echo.
echo %YELLOW%[INFO]%RESET% Verifying build output...
if not exist "dist\ble_bridge.exe" (
    echo %RED%[ERROR]%RESET% Build output not found: dist\ble_bridge.exe
    exit /b 1
)

:: Get file size
for %%A in ("dist\ble_bridge.exe") do set size=%%~zA
set /a size_mb=!size! / 1048576
echo %GREEN%[OK]%RESET% Executable created: dist\ble_bridge.exe (!size_mb! MB)

:: Build summary
echo.
echo %GREEN%========================================
echo   Backend Build Completed Successfully
echo ========================================%RESET%
echo.
echo %GREEN%[SUCCESS]%RESET% Output: windows-listener\dist\ble_bridge.exe
echo %GREEN%[SUCCESS]%RESET% Size: !size_mb! MB
echo %GREEN%[SUCCESS]%RESET% Type: Standalone executable
echo.

exit /b 0