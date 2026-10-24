@echo off
rem Run the Mercado Libre credentials setup.
rem Place this file in the project root (the folder that contains "src").

cd /d "%~dp0"
set PYTHONPATH=src

python -m app_name.integrations.mercado_libre.credentials_manager.__main__

echo.
pause
