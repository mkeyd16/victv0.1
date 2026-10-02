@echo off
setlocal enabledelayedexpansion

echo Checking Python 3.14 installation...
py -3.14 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.14 is not installed or 'py -3.14' is not available.
    echo Please install Python 3.14 on your system before running Vict.
    pause
    exit /b 1
)

echo Checking required Python packages (discord.py and llama-cpp-python)...
py -3.14 -c "import discord; from llama_cpp import Llama" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Required Python packages are missing.
    echo Please ensure discord.py and llama-cpp-python are installed in Python 3.14.
    pause
    exit /b 1
)

echo Checking GGUF model file...
if not exist "models\SmolLM2-360M-Instruct-Q4_K_M.gguf" (
    echo [ERROR] Model file 'models\SmolLM2-360M-Instruct-Q4_K_M.gguf' was not found.
    echo Please place SmolLM2-360M-Instruct-Q4_K_M.gguf inside the models\ directory.
    pause
    exit /b 1
)

echo All checks passed! Starting Vict...
py -3.14 bot.py
if %errorlevel% neq 0 (
    echo [ERROR] Vict exited with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)
