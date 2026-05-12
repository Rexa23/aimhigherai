@echo off
REM AimHigher Quick Setup Script for Windows

echo.
echo 🚀 AimHigher AI Setup
echo ====================
echo.

REM Check for .env file
if not exist .env (
    echo ⚠️  .env file not found
    echo 📋 Copying .env.example to .env...
    copy .env.example .env
    echo ✅ .env created - edit with your values
) else (
    echo ✅ .env exists
)

REM Check for frontend .env.local
if not exist frontend\.env.local (
    echo ⚠️  frontend\.env.local not found
    echo 📋 Copying template...
    copy frontend\.env.local.example frontend\.env.local
    echo ✅ frontend\.env.local created
) else (
    echo ✅ frontend\.env.local exists
)

REM Check for logo
if not exist frontend\public\logo.png (
    echo.
    echo ⚠️  Logo not found!
    echo 📸 Please save your logo image as: frontend\public\logo.png
    echo    Then update frontend\src\components\landing\Navbar.tsx line 31:
    echo    Change src="/aimhigher-logo.svg" to src="/logo.png"
) else (
    echo ✅ Logo found
)

echo.
echo 📦 Installing dependencies...
cd frontend
call npm install
cd ..

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Edit .env with your API keys
echo 2. Edit frontend\.env.local if needed
echo 3. Place your logo at: frontend\public\logo.png
echo 4. Run: docker-compose up --build
echo.

pause
