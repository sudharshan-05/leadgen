# 🚀 Free Cloud Deployment Guide — Lead Intelligence Bot

> Deploy your Telegram bot so it runs **24/7 even when your laptop is off**, completely free, for you and all your friends.

---

## ✅ What Was Fixed (Bugs Resolved)

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `[Errno 13] Permission denied: 'outputs\...'` | `OUTPUTS_FOLDER` pointed to a Windows path, not writable in Docker | `config/settings.py` now auto-detects writable folder; `EXPORTS_FOLDER=/app/exports` set in Docker |
| Bot stops when laptop turns off | Bot was running locally on your machine | Deploy to Railway.app cloud — always running |
| Bot not working for friends | Bot only responded from your local IP | Cloud deployment makes the bot globally available |
| Redis/DB connection refused at startup | Services starting before DB was ready | Added `healthcheck` to Redis; all services now wait for `service_healthy` |

---

## 🏗️ Architecture (What Runs Where)

```
Railway Cloud (Free)
├── 🤖 Bot Service     → Telegram polling (always on)
├── ⚙️  Celery Worker  → Background lead scraping
├── 📅 Scheduler       → Runs daily/weekly campaigns
├── 👁️  Watchdog       → Self-heals crashed jobs
├── 🗄️  PostgreSQL     → Lead + job database
└── ⚡ Redis           → Task queue broker
```

---

## 📦 Option A: Deploy on Railway.app (Recommended — Truly Free)

Railway gives **$5 free credits/month** — enough to run the bot, worker, Redis, and Postgres 24/7.

### Step 1 — Push your code to GitHub

```bash
# In your lead_agent folder:
git init
git add .
git commit -m "Production-ready Lead Agent bot"

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/lead-agent.git
git push -u origin main
```

> ⚠️ **IMPORTANT**: Your `.env` file is in `.gitignore` — secrets are NOT uploaded to GitHub. Good!

---

### Step 2 — Create Railway account and project

1. Go to **[railway.app](https://railway.app)** → Sign up with GitHub
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select your `lead-agent` repository
4. Railway will detect the `Dockerfile` automatically

---

### Step 3 — Add PostgreSQL database

In your Railway project dashboard:
1. Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway creates a free Postgres instance
3. Click on the Postgres service → **"Variables"** tab
4. Copy the `DATABASE_URL` value shown there

---

### Step 4 — Add Redis

1. Click **"+ New"** → **"Database"** → **"Redis"**
2. Railway creates a free Redis instance
3. Click on the Redis service → **"Variables"** tab
4. Copy the `REDIS_URL` value shown there

---

### Step 5 — Set Environment Variables

In your **main app service** on Railway, go to **Variables** tab and add:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8896713978:AAFaJRzCjFTpBDwi55K1_1oYgUTzgCuDoVg` |
| `DATABASE_URL` | *(paste from Railway Postgres step above)* |
| `REDIS_URL` | *(paste from Railway Redis step above)* |
| `ENV` | `production` |
| `EXPORTS_FOLDER` | `/app/exports` |

---

### Step 6 — Deploy the Celery Worker service

Your bot needs a separate worker to run scraping in background:

1. In Railway dashboard → click **"+ New"** → **"GitHub Repo"** (same repo)
2. In this new service settings → **"Start Command"**:
   ```
   celery -A workers.celery_app worker --loglevel=info --concurrency=1
   ```
3. Add the **same environment variables** as above

---

### Step 7 — Verify deployment

Once deployed, send `/start` to your bot on Telegram. You should see the help menu.

Send `/status` — you should see system status with 0 leads (fresh database).

**Your bot is now live 24/7 even when your laptop is off! 🎉**

---

## 📦 Option B: Run with Docker on your own server (VPS/Oracle Cloud)

If you have a VPS (Oracle Cloud Free Tier, Google Cloud Free Tier, etc.):

```bash
# On your VPS/server:
git clone https://github.com/YOUR_USERNAME/lead-agent.git
cd lead-agent

# Create your .env file
cp .env.example .env
nano .env  # Fill in your TELEGRAM_BOT_TOKEN

# Build and start all services
docker-compose up --build -d

# Verify all services are running
docker-compose ps

# Check bot logs
docker-compose logs -f bot

# Check worker logs  
docker-compose logs -f celery_worker
```

---

## 🧪 Test the Bot (Send These Commands)

After deployment, test with your Telegram:

```
/start          → Should show help menu with all commands
/status         → Should show database stats
/find 5 dentist Chennai     → Runs a test scrape for 5 leads
```

---

## 🔧 Troubleshooting

### Bot not responding?
- Check Railway logs → click your bot service → "Logs" tab
- Verify `TELEGRAM_BOT_TOKEN` is set correctly in Variables

### "Connection refused" database error?
- Make sure `DATABASE_URL` variable is set (Railway Postgres URL, not `@db:5432`)
- On Railway, the DB URL format is: `postgresql://user:pass@HOST.railway.app:PORT/railway`

### "Permission denied" on file export?
- Make sure `EXPORTS_FOLDER=/app/exports` is set
- This is fixed in the new `config/settings.py` automatically

### Bot works but scraping returns 0 leads?
- This is normal on first run — Playwright needs to warm up
- Try `/find 10 restaurant Chennai` and wait 3-5 minutes

---

## 💰 Cost Summary

| Service | Provider | Monthly Cost |
|---------|----------|-------------|
| Bot + Worker | Railway | Free ($5 credit covers it) |
| PostgreSQL | Railway | Free (included) |
| Redis | Railway | Free (included) |
| **Total** | | **$0/month** |

---

## 📞 Support

If the bot still doesn't work after following these steps:
1. Run the pre-check: `python railway_env_check.py`
2. Check Railway deployment logs for error messages
3. Verify your Telegram bot token at [BotFather](https://t.me/BotFather)
