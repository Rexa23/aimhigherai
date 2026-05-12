# 🚀 AimHigher Deployment Guide

## ⚠️ Security First - Hide API Keys

Never commit `.env` files. The project is configured to:
- ✅ Exclude `.env` via `.gitignore`
- ✅ Use `.env.example` for reference
- ✅ Load secrets from platform environment variables

## 🌐 Frontend Deployment (Vercel Recommended)

### Step 1: Prepare for Vercel
```bash
cd frontend
npm run build
vercel deploy --prod
```

### Step 2: Add Environment Variables in Vercel Dashboard
Settings → Environment Variables:
```
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

## 🔧 Backend Deployment (Docker + Railway Recommended)

### Step 1: Set Up Railway Project
1. Connect your GitHub repository
2. Create PostgreSQL service
3. Create Redis service
4. Create Docker service for backend

### Step 2: Add Secrets to Railway
In Railway Dashboard → Variables:
```
POSTGRES_PASSWORD=<strong-random-value>
REDIS_PASSWORD=<strong-random-value>
SECRET_KEY=<strong-random-value>
DATABASE_URL=postgresql://user:pass@postgres:5432/aimhigher
GEMINI_API_KEY=<your-api-key>
OPENAI_API_KEY=<your-api-key>
FRONTEND_URL=https://your-frontend.vercel.app
```

### Step 3: Deploy
Railway auto-deploys on git push.

## 🔐 API Key Rotation

If keys are ever exposed:
1. Immediately revoke the old key in the API provider's dashboard
2. Generate a new key
3. Update in your deployment platform
4. Redeploy (usually automatic)

## ✅ Pre-Deployment Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] `.env` contains placeholder values only
- [ ] All real secrets added to platform (Vercel, Railway, etc)
- [ ] Run `npm run build` successfully
- [ ] Backend `.env` matches `.env.example` structure
- [ ] FRONTEND_URL set to production domain
- [ ] NEXT_PUBLIC_API_URL points to production backend
- [ ] Database migrations run successfully
- [ ] Test API connectivity from deployed frontend

## 📝 Vercel Deployment (Step-by-Step)

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. From frontend directory
cd frontend

# 3. Deploy
vercel --prod

# 4. Add env vars in Vercel Dashboard
# Settings → Environment Variables → Add NEXT_PUBLIC_API_URL

# 5. Redeploy with env vars
vercel --prod
```

## 🐳 Docker Deployment (Self-Hosted)

```bash
# Build and run locally
docker-compose up --build

# For production:
# 1. Use Railway, Heroku, or AWS ECS
# 2. Set environment variables in platform
# 3. The docker-compose.yml handles the rest
```

## 🔗 Update CORS & URLs

After deployment, update in `.env`:
```
FRONTEND_URL=https://your-frontend.vercel.app
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

## 🆘 Troubleshooting

### Frontend won't connect to backend
- Check `NEXT_PUBLIC_API_URL` in Vercel env vars
- Verify backend is running and accessible
- Check CORS settings in backend (`ALLOWED_ORIGINS`)

### API keys appear in build output
- Make sure they're NOT prefixed with `NEXT_PUBLIC_`
- Only `NEXT_PUBLIC_*` vars leak to browser
- Sensitive keys must NOT have `NEXT_PUBLIC_` prefix

### Database connection fails
- Verify `DATABASE_URL` environment variable
- Check database service is running
- Run migrations: `alembic upgrade head`

---

**Your app is production-ready! 🎉**
