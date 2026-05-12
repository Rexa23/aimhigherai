# 🚀 Quick Reference - Deployment Commands

## 🎨 Add Your Logo

**1. Save the PNG image you provided to:**
```
frontend/public/logo.png
```

**2. (Optional) Update Navbar to use it:**
Edit `frontend/src/components/landing/Navbar.tsx` line 31 - change:
```tsx
src="/aimhigher-logo.svg"
// to:
src="/logo.png"
```

---

## 🖥️ Local Development

### With Docker (Recommended)
```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

### Frontend Only
```bash
cd frontend
npm run dev
# http://localhost:3000
```

---

## 🌐 Deploy to Production

### Frontend → Vercel (5 minutes)
```bash
cd frontend

# First time
vercel

# Production deploy
vercel deploy --prod

# Then add in Vercel Dashboard:
# Settings → Environment Variables
# NEXT_PUBLIC_API_URL = https://api.your-domain.com
```

### Backend → Railway (10 minutes)
1. Go to [railway.app](https://railway.app)
2. New Project → GitHub Repo
3. Create PostgreSQL service
4. Create Redis service
5. Create Docker service
6. Add environment variables (see .env.example)
7. Deploy!

---

## 🔐 API Keys - STAY SECURE

### ✅ DO:
```bash
# Backend .env (server-side only)
GEMINI_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
```

### ❌ DON'T:
```bash
# Frontend (EXPOSED to browser)
NEXT_PUBLIC_GEMINI_API_KEY=sk-xxx  # ❌ NO!
NEXT_PUBLIC_OPENAI_API_KEY=sk-xxx  # ❌ NO!
```

---

## 📋 File Reference

| File | Purpose |
|------|---------|
| `.env` | Development secrets (⚠️ .gitignored) |
| `.env.example` | Template (safe to commit) |
| `DEPLOYMENT.md` | Full deployment guide |
| `SETUP.md` | Complete setup instructions |
| `SECURITY_READY.md` | Security verification report |
| `setup.sh` | Auto-setup for macOS/Linux |
| `setup.bat` | Auto-setup for Windows |

---

## ✅ Pre-Deploy Checklist

```
□ Logo saved to frontend/public/logo.png
□ npm run build = ✓ Compiled successfully
□ .env file contains dummy values (not secrets)
□ .env.example has the template
□ .gitignore excludes .env ✓
□ All .env vars are non-production placeholders
□ API keys ready (not committed)
```

---

## 🆘 Troubleshooting

### Frontend won't build
```bash
cd frontend
rm -rf .next node_modules
npm install
npm run build
```

### Backend can't connect
- Check DATABASE_URL in .env
- Verify PostgreSQL is running
- Run: `alembic upgrade head`

### API keys showing in build
- Remove `NEXT_PUBLIC_` prefix from sensitive vars
- Check `next.config.js` has `env: {}`
- Rebuild: `npm run build`

---

## 📞 Quick Links

- 📚 [DEPLOYMENT.md](DEPLOYMENT.md) - Step-by-step deployment
- 🛠️ [SETUP.md](SETUP.md) - Full setup guide
- 🔐 [SECURITY_READY.md](SECURITY_READY.md) - Security verification
- 🌐 [Vercel Docs](https://vercel.com/docs)
- 🚂 [Railway Docs](https://docs.railway.app)

---

**Your app is production-ready with enterprise security! 🎉**
