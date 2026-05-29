@echo off
REM NeMo Environment Setup Script for Windows
REM This script sets up the NeMo environment and dependencies

setlocal

REM Configuration
set BRANCH=main
set NEMO_DIR=NeMo

echo Setting up NeMo environment...

echo Cloning NeMo repository...
git clone -b %BRANCH% https://github.com/NVIDIA/NeMo %NEMO_DIR%
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to clone NeMo repository
    exit /b 1
)

echo Installing NeMo...
python -m pip install "git+https://github.com/NVIDIA/NeMo.git@main#egg=nemo_toolkit"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install NeMo
    exit /b 1
)

echo NeMo environment setup completed successfully!
pause