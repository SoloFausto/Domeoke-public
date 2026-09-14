@echo off
setlocal
python "%~dp0setup.py" %*
exit /b %ERRORLEVEL%
