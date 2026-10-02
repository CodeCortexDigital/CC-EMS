@echo off
REM Loads the sample US school (Maple Grove Academy: 214 students, 24 staff, timetable, fees, attendance, exams, HR)
REM into the demo database and makes the demo logins open it. Stop the demo first, then run restart-demo.bat.
setlocal
set DEBUG=1
set USE_SQLITE=1
cd /d "%~dp0backend"
.venv\Scripts\python manage.py migrate --noinput || goto :fail
.venv\Scripts\python manage.py seed_sample_users --force
.venv\Scripts\python manage.py seed_demo --pack us-school --reset || goto :fail
echo.
echo Done. Start the demo (restart-demo.bat) and log in as admin@code.com / Admin@123.
exit /b 0
:fail
echo Failed - see the messages above.
exit /b 1
