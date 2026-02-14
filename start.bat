@echo off
echo ============================================
echo   DataChat - Conversational Analytics API
echo ============================================
echo.

REM Check if .env exists
if not exist .env (
    echo [WARNING] No .env file found. Copying from env.example...
    copy env.example .env
    echo [INFO] Please edit .env and set your GCP_PROJECT_ID
    echo.
)

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [INFO] Virtual environment activated.
) else (
    echo [INFO] No virtual environment found. Using system Python.
    echo [TIP] Create one with: python -m venv venv
)

echo.
echo Starting DataChat...
echo Open your browser at: http://localhost:8501
echo.

streamlit run app.py
