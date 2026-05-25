@echo off
cd /d "%~dp0"
echo Video Automation Studio
echo ========================

if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt -q

python main.py
pause
