#!/bin/bash
# AimHigher Quick Setup Script

echo "🚀 AimHigher AI Setup"
echo "===================="
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    echo "📋 Copying .env.example to .env..."
    cp .env.example .env
    echo "✅ .env created - edit with your values"
else
    echo "✅ .env exists"
fi

# Check for frontend .env.local
if [ ! -f frontend/.env.local ]; then
    echo "⚠️  frontend/.env.local not found"
    echo "📋 Copying template..."
    cp frontend/.env.local.example frontend/.env.local
    echo "✅ frontend/.env.local created"
else
    echo "✅ frontend/.env.local exists"
fi

# Check for logo
if [ ! -f frontend/public/logo.png ]; then
    echo ""
    echo "⚠️  Logo not found!"
    echo "📸 Please save your logo image as: frontend/public/logo.png"
    echo "   Then update frontend/src/components/landing/Navbar.tsx line 31:"
    echo "   Change src=\"/aimhigher-logo.svg\" to src=\"/logo.png\""
else
    echo "✅ Logo found"
fi

echo ""
echo "📦 Installing dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Edit frontend/.env.local if needed"
echo "3. Place your logo at: frontend/public/logo.png"
echo "4. Run: docker-compose up --build"
echo ""
