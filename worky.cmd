@echo off
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
set "__WORKY_VENV=%~dp0.venv\Scripts\python.exe"
if exist "%__WORKY_VENV%" (
  "%__WORKY_VENV%" -m worky %*
) else (
  py -m worky %*
)
endlocal
