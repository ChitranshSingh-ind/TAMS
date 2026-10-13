@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  TAMS Windows Automated Build Script (TAMS + CoachingHelper)
echo =====================================================================

:: 1. Check Python installation
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv...
    python -m venv .venv
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 3. Install and Upgrade Dependencies
echo [INFO] Installing required dependencies from requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:: 4. Synchronize Database Migrations
echo [INFO] Synchronizing Alembic database migrations...
alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Database migration failed. Please check migration scripts.
    pause
    exit /b 1
)

:: 5. Build Executables with PyInstaller
echo [INFO] Building standalone directory bundle with PyInstaller...
pyinstaller --clean --noconfirm tams.spec
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed. Check console output above.
    pause
    exit /b 1
)

:: 6. Verify Build Artifacts
if not exist "dist\TAMS\TAMS.exe" (
    echo [ERROR] Build verification failed: dist\TAMS\TAMS.exe not found.
    pause
    exit /b 1
)

if not exist "dist\TAMS\CoachingHelper.exe" (
    echo [ERROR] Build verification failed: dist\TAMS\CoachingHelper.exe not found.
    pause
    exit /b 1
)

echo [SUCCESS] Binary build complete:
echo   - Main Application: dist\TAMS\TAMS.exe
echo   - Companion Daemon: dist\TAMS\CoachingHelper.exe

:: 7. Compile Inno Setup Installer (if Inno Setup is installed)
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if exist "%ISCC_PATH%" (
    echo [INFO] Compiling Windows Installer with Inno Setup...
    "%ISCC_PATH%" installer.iss
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] Installer successfully created in Output\
    ) else (
        echo [WARNING] Inno Setup compilation encountered an issue.
    )
) else (
    echo [NOTE] Inno Setup 6 was not detected at standard locations.
    echo        To generate TAMS_Setup_v2.0.0.exe, install Inno Setup 6 and run:
    echo        ISCC.exe installer.iss
)

echo =====================================================================
echo  Build Process Finished Successfully!
echo =====================================================================
exit /b 0
