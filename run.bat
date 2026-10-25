@echo off
setlocal
set "PYTHONPATH=%~dp0src"
python -m depgraph %*
exit /b %ERRORLEVEL%
