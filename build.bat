@echo off
setlocal enabledelayedexpansion

:: Colors and formatting
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RESET=[0m"

:: Get timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set timestamp=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2% %datetime:~8,2%:%datetime:~10,2%:%datetime:~12,2%

:: Setup logging
set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\build_%datetime:~0,8%_%datetime:~8,6%.log"

call :log "======================================================================"
call :log "              ELECTRON + BACKEND BUILD STARTED"
call :log "======================================================================"
call :log "Build Time: %timestamp%"
call :log "Log File: %LOG_FILE%"
call :log ""

cd /d %~dp0

:: Build Backend
call :log_header "STEP 1/2: Building Python Backend"
call build_backend.bat
if !errorlevel! neq 0 (
    call :log_error "Backend build FAILED with error code: !errorlevel!"
    call :log_error "Check log file for details: %LOG_FILE%"
    goto :build_failed
)
call :log_success "Backend build completed successfully"
call :log ""

:: Build Frontend
call :log_header "STEP 2/2: Building Electron Frontend"
call build_frontend.bat
if !errorlevel! neq 0 (
    call :log_error "Frontend build FAILED with error code: !errorlevel!"
    call :log_error "Check log file for details: %LOG_FILE%"
    goto :build_failed
)
call :log_success "Frontend build completed successfully"
call :log ""

:: Success
call :log "======================================================================"
call :log_success "           BUILD COMPLETED SUCCESSFULLY!"
call :log "======================================================================"
call :log "Total Steps: 2/2 completed"
call :log "Build artifacts ready for deployment"
call :log ""
exit /b 0

:build_failed
call :log "======================================================================"
call :log_error "                BUILD FAILED!"
call :log "======================================================================"
call :log_error "Please check the error messages above and try again"
call :log ""
exit /b 1

:: Logging functions
:log
echo %~1
echo [%time%] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:log_header
echo.
echo %BLUE%========================================%RESET%
echo %BLUE%%~1%RESET%
echo %BLUE%========================================%RESET%
echo [%time%] ======================================== >> "%LOG_FILE%" 2>&1
echo [%time%] %~1 >> "%LOG_FILE%" 2>&1
echo [%time%] ======================================== >> "%LOG_FILE%" 2>&1
exit /b 0

:log_success
echo %GREEN%[SUCCESS]%RESET% %~1
echo [%time%] [SUCCESS] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:log_error
echo %RED%[ERROR]%RESET% %~1
echo [%time%] [ERROR] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0