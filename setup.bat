@echo off
REM Setup script for Rescue Agent MCP on Windows

echo.
echo ================================================
echo   Rescue Agent MCP v2.0 - Windows Setup
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python 3.11+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

echo [1/4] Python found
python --version

REM Create virtual environment
echo.
echo [2/4] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    echo Virtual environment created
)

REM Activate virtual environment
echo.
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo [4/4] Installing dependencies...
echo This may take a few minutes...
pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo.
    echo Try installing manually:
    echo    venv\Scripts\activate
    echo    pip install openai python-dotenv pydantic httpx aiohttp loguru pytest pytest-asyncio tenacity cachetools python-dateutil pytest-mock mcp
    pause
    exit /b 1
)

REM Create .env file
echo.
echo [5/5] Setting up configuration...
if exist .env (
    echo .env file already exists
) else (
    copy .env.example .env
    echo Created .env file from template
    echo.
    echo IMPORTANT: Edit .env and add your OpenAI API key!
    echo    notepad .env
)

echo.
echo ================================================
echo   Setup Complete!
echo ================================================
echo.
echo Next steps:
echo   1. Edit .env file and add your OpenAI API key
echo      ^> notepad .env
echo.
echo   2. Run the demo:
echo      ^> python demo.py
echo.
echo   3. Read the documentation:
echo      ^> README.md - Overview
echo      ^> MCP_GUIDE.md - Detailed MCP guide
echo.
pause
