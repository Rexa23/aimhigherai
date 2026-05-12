# 🚀 AimHigher AI Setup & Deployment Guide

## 📦 Project Structure

```
aimhigher/
├── frontend/              # Next.js 14 landing page + dashboard
│   ├── src/
│   │   ├── app/          # Pages
│   │   ├── components/   # React components
│   │   └── lib/          # Utilities & API client
│   ├── public/           # Static assets (logo goes here)
│   └── package.json
├── backend/              # Python FastAPI + Agents
│   ├── app/
│   │   ├── agents/       # Hunter, Outreach, Qualification, Onboarding
│   │   ├── api/          # REST endpoints
│   │   ├── db/           # Database models
│   │   └── services/     # AI services
│   ├── alembic/          # Database migrations
│   └── requirements.txt
├── docker-compose.yml    # Development environment
├── .env                  # Configuration (⚠️ .gitignore'd)
├── .env.example          # Template
└── DEPLOYMENT.md         # Deployment instructions
```

## 🎨 Adding Your Logo

The logo image you provided needs to be saved as a PNG file:

### Step 1: Save Logo Image
1. **Right-click** on your logo image
2. **Save As** to: `frontend/public/logo.png`
3. The path should be: `frontend/public/logo.png`

### Step 2: Logo Already Integrated
The Navbar will automatically use the logo from `frontend/public/aimhigher-logo.svg`. 

**To use your PNG instead:**
Update [Navbar.tsx](frontend/src/components/landing/Navbar.tsx) line 31:
```tsx
// Change from:
src="/aimhigher-logo.svg"

// To:
src="/logo.png"
```

---

## 🏗️ Local Development Setup

### Prerequisites
- Node.js 18+
- Python 3.10+
- Docker & Docker Compose
- Git

### Step 1: Clone & Install
```bash
# Frontend
cd frontend
npm install

# Backend (optional - only if running locally without Docker)
cd ../backend
pip install -r requirements.txt
```

### Step 2: Environment Setup
```bash
# Copy template to actual env file
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local

# Edit .env with your values:
# - Generate secure passwords
# - Add API keys (Gemini, OpenAI)
```

### Step 3: Run Development

**Option A: With Docker (Recommended)**
```bash
# From root directory
docker-compose up --build
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

**Option B: Frontend Only**
```bash
cd frontend
npm run dev
# Frontend: http://localhost:3000
# Connects to backend at http://localhost:8000
```

---

## 🔐 Security Best Practices

### ✅ Already Configured
- `.env` files excluded from git (`.gitignore`)
- API keys not exposed to frontend (only `NEXT_PUBLIC_*` variables)
- Environment variables only used server-side
- Security headers configured in `next.config.js`

### 🛡️ API Key Management

**DO NOT:**
```bash
# ❌ Wrong - keys will leak to browser
NEXT_PUBLIC_GEMINI_API_KEY=sk-xxx
NEXT_PUBLIC_OPENAI_API_KEY=sk-xxx
```

**DO:**
```bash
# ✅ Correct - server-side only (no NEXT_PUBLIC_ prefix)
GEMINI_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
```

---

## 📊 Production Deployment

### Frontend → Vercel
```bash
cd frontend
vercel --prod
```
Then add environment variables in Vercel Dashboard:
```
NEXT_PUBLIC_API_URL=https://api.aimhigher.xyz
```

### Backend → Railway
1. Connect GitHub repo
2. Add PostgreSQL + Redis services
3. Add Backend service (Docker)
4. Set environment variables in Railway Dashboard

**See `DEPLOYMENT.md` for detailed instructions**

---

## 🗄️ Database

### Migrations
```bash
# Run migrations
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new column"
```

### Seeding
Backend will auto-seed on first run. Check `backend/app/main.py`.

---

## 🔧 Environment Variables Reference

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (`.env`)
```
# Infrastructure
POSTGRES_PASSWORD=secure-password
REDIS_PASSWORD=secure-password
SECRET_KEY=32-character-random-string

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/aimhigher

# APIs
GEMINI_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here

# Frontend (for CORS)
FRONTEND_URL=http://localhost:3000
```

---

## ✅ Pre-Production Checklist

- [ ] Logo saved to `frontend/public/logo.png`
- [ ] All `.env` values filled in
- [ ] Database migrations ran successfully
- [ ] `npm run build` completes without errors
- [ ] Backend health check passes
- [ ] Frontend loads and connects to backend
- [ ] API keys rotated/secured
- [ ] `.env` file is in `.gitignore` ✅ (already done)
- [ ] `NEXT_PUBLIC_API_URL` set for production

---

## 🚀 Deploy in 5 Minutes

### Local to Vercel (Frontend)
```bash
cd frontend
vercel deploy --prod
# Add NEXT_PUBLIC_API_URL to Vercel Dashboard
```

### Local to Railway (Backend)
```bash
# Connect your GitHub repo to Railway
# Select Dockerfile
# Add environment variables
# Deploy!
```

---

## 📞 Support

For API issues:
- Check backend logs: `docker-compose logs backend`
- Check frontend console: F12 in browser
- Verify `.env` configuration

For deployment issues:
- See `DEPLOYMENT.md`
- Check platform-specific docs (Vercel, Railway)

---

**🎉 You're production-ready!**
