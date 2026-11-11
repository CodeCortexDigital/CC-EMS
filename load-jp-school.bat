@echo off
REM Loads the sample Japanese school (Wakaba Gakuen: 109 students in grades 1-9, 27 staff, timetable, school lunch fees in yen, attendance, exams)
REM into the demo database and makes the demo logins open it. Stop the demo first, then run restart-demo.bat.
REM Switch back to the US school with load-us-school.bat.
setlocal
set DEBUG=1
set PYTHONUTF8=1
set USE_SQLITE=1
cd /d "%~dp0backend"
.venv\Scripts\python manage.py migrate --noinput || goto :fail
.venv\Scripts\python manage.py seed_sample_users --force
.venv\Scripts\python manage.py seed_demo --pack jp-school --reset || goto :fail
echo.
echo Done. Start the demo (restart-demo.bat), log in as admin@code.com / Admin@123, and choose 日本語 with the globe button on the sign-in page.
exit /b 0
:fail
echo Failed - see the messages above.
exit /b 1
