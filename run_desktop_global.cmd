@echo off
rem Launch AirCanvas with the global Python 3.15.1 (not the project venv).
rem This is the recommended launcher when the webcam is only visible to the
rem globally installed Python + OpenCV.
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3.15 run_desktop.py --camera-backend auto --no-onboarding %*
) else (
  python run_desktop.py --camera-backend auto --no-onboarding %*
)
