@echo off
setlocal

set REPO_URL=https://github.com/prankapple/ThreadCrawl.git
set DIR_NAME=ThreadCrawl

echo 🔽 Cloning ThreadCrawl...
if exist "%DIR_NAME%" (
    echo ⚠️ Directory "%DIR_NAME%" already exists. Skipping clone.
) else (
    git clone %REPO_URL%
    if errorlevel 1 goto error
)

cd "%DIR_NAME%" || goto error

echo 🐍 Installing Python dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto error

python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo ✅ Installation complete!
cd ThreadCrawl
echo ▶ Run with: cd ThreadCrawl && python crawler.py
echo.

pause
exit /b 0

:error
echo.
echo ❌ Installation failed.
pause
exit /b 1


