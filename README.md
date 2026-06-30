# Telegram Lead Intelligence Agent — Production Edition

A cloud-native, fault-tolerant, self-healing Lead Intelligence platform containerized using Docker, backed by PostgreSQL, queued via Celery & Redis, and scheduled with APScheduler.

---

## Architecture Overview

```
                        ┌───────────────────┐
                        │   Telegram User   │
                        └─────────┬─────────┘
                                  │ Commands / Natural Text
                                  ▼
                        ┌───────────────────┐
                        │   Telegram Bot    │
                        └─────────┬─────────┘
                                  │ Enqueues Celery Tasks
                                  ▼
┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐
│   APScheduler    ├───►│       Redis       │◄───┤   Self-Healing   │
│ (Campaign Cron)  │    │   (Task Queue)    │    │   Watchdog Loop  │
└──────────────────┘    └─────────┬─────────┘    └──────────────────┘
                                  │
                                  ▼
                        ┌───────────────────┐
                        │   Celery Worker   │◄─── Playwright + Headless Chromium
                        └─────────┬─────────┘
                                  │ Runs Scrapers & Auditing
                                  ▼
                        ┌───────────────────┐
                        │    PostgreSQL     │
                        │    (DB Engine)    │
                        └───────────────────┘
```

---

## Production Project Layout

```
lead-agent/
│
├── bot/                         # Telegram Bot Service
│   ├── __init__.py
│   └── bot_app.py               # Main bot handlers
│
├── api/                         # Health Check & Monitoring API
│   ├── __init__.py
│   └── main.py                  # FastAPI server
│
├── scrapers/                    # Base & Concrete Scraping Modules
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── google_maps.py           # Playwright Maps scraper
│   ├── google_search.py         # Playwright Search scraper
│   ├── justdial.py              # Directory scraper
│   ├── sulekha.py               # Directory scraper
│   └── orchestrator.py          # Parallel execution pipeline
│
├── workers/                     # Celery Workers & Self-Healing Agent
│   ├── __init__.py
│   ├── celery_app.py            # Celery configurations
│   ├── tasks.py                 # Asynchronous background tasks
│   └── self_healing.py          # Autonomous cleanup and repair daemon
│
├── scheduler/                   # APScheduler Campaigns Service
│   ├── __init__.py
│   └── scheduler.py             # Watchdog cron dispatcher
│
├── database/                    # SQLAlchemy ORM Database Layer
│   ├── __init__.py
│   ├── connection.py            # Engine and Session context provider
│   ├── models.py                # Database schemas mapping
│   └── crud.py                  # CRUD helper operations
│
├── monitoring/                  # Sentry & Rotating Logger
│   ├── __init__.py
│   ├── logger.py                # Rotating File Logger
│   └── sentry.py                # Sentry SDK wrappers
│
├── analytics/                   # Data Enrichment and Scoring Layers
│   ├── __init__.py
│   ├── activity_detector.py     # Layer 1: Activity detection
│   ├── website_analyser.py      # Layer 2+3: Website technical audit
│   ├── email_finder.py          # Layer 4: Email discovery & MX verification
│   ├── business_intelligence.py # Layer 5: Company profile extraction
│   ├── pain_point_engine.py     # Layer 6+7: Pitches and recommended services
│   ├── scorer.py                # Layer 8: Scoring & filters qualification
│   ├── dedup.py                 # Multi-factor token deduplicator
│   └── exporter.py              # Multi-sheet Excel report builder
│
├── logs/                        # Rotating log files storage
├── exports/                     # Generated Excel spreadsheets
├── Dockerfile                   # Unified application container blueprint
├── docker-compose.yml           # Complete system service definitions
├── requirements.txt             # Central dependencies
├── .env.example                 # Environment variables blueprint
├── main.py                      # Root CLI runner / service selector
└── README.md                    # This file
```

---

## Quick Start (Local Docker Setup)

Ensure you have **Docker** and **Docker Compose** installed on your system.

1. **Clone/Move to project directory**
2. **Configure Environment Variables**:
   Copy `.env.example` into a new file named `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your details:
   - `TELEGRAM_BOT_TOKEN`: The API key generated from Telegram BotFather.
   - `SENTRY_DSN`: Your Sentry SDK URL (optional).

3. **Start the Platform**:
   Build and start all services with a single command:
   ```bash
   docker-compose up --build -d
   ```
   This will spin up:
   * PostgreSQL (`lead_agent_db` on port 5432)
   * Redis (`lead_agent_redis` on port 6379)
   * Monitoring API (`lead_agent_api` on port 8000)
   * Celery Workers (`lead_agent_worker`)
   * Campaign Scheduler (`lead_agent_scheduler`)
   * Telegram Bot Client (`lead_agent_bot`)
   * Autonomous Watchdog (`lead_agent_watchdog`)

4. **Verify Systems Health**:
   Execute curl to verify the API response:
   ```bash
   curl http://localhost:8000/health
   ```

---

## Deployment Guidelines

### Target 1: Render

To deploy the platform on Render:
1. **Host PostgreSQL database**:
   * Create a new PostgreSQL instance on Render.
   * Copy the internal/external database URL.
2. **Deploy Redis instance**:
   * Create a Redis instance on Render.
   * Copy the connection URL.
3. **Deploy Web API (FastAPI Health Checks)**:
   * Create a **Web Service** on Render, linking to your repository.
   * Root Directory: `./` (or leave empty).
   * Runtime: `Docker`.
   * Plan: Starter (Requires standard resources for Chromium execution).
   * Set Environment variables:
     * `ENV=production`
     * `DATABASE_URL=your_render_postgres_url`
     * `REDIS_URL=your_render_redis_url`
     * `TELEGRAM_BOT_TOKEN=your_bot_token`
4. **Deploy Background Workers (Bot, Scheduler, Worker, Watchdog)**:
   * Create **Background Workers** on Render for each service:
     * **Bot Service**: Docker Command `python main.py --service bot`
     * **Celery Worker**: Docker Command `celery -A workers.celery_app worker --loglevel=info --concurrency=1`
     * **Scheduler**: Docker Command `python main.py --service scheduler`
     * **Watchdog**: Docker Command `python main.py --service agent`
   * Reuse the same environment variables across all services.

---

### Target 2: Koyeb

Koyeb offers native Docker and git deployments:
1. **Deploy Redis & Postgres Databases**:
   * Provision Postgres and Redis from the Koyeb marketplace or use your preferred hosted instances.
2. **Deploy Platform App via Git**:
   * Link your repository and set builder settings to **Docker**.
   * Define Koyeb services:
     * `api`: Port 8000 (Exposed public endpoint). Docker Command: `python main.py --service api`
     * `bot`: Private worker. Docker Command: `python main.py --service bot`
     * `worker`: Private worker. Docker Command: `celery -A workers.celery_app worker --loglevel=info --concurrency=1`
     * `scheduler`: Private worker. Docker Command: `python main.py --service scheduler`
     * `watchdog`: Private worker. Docker Command: `python main.py --service agent`
   * Map all credentials via Koyeb Secrets Manager.

---

### Target 3: Oracle Cloud Free Tier (Compute VM Instance)

For a fully controlled deployment, Oracle Cloud Free Tier provides ARM/AMD instances.

1. **Spin up Ubuntu VM Instance** (e.g. 4 OCPUs, 24 GB RAM Ampere instance).
2. **Allow Network Ports**: Open ports `80` (HTTP), `443` (HTTPS), and `8000` (API) on both the VM iptables and security list rules.
3. **SSH into the VM and install Docker + Docker Compose**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose
   sudo systemctl enable --now docker
   ```
4. **Clone the repository onto the instance**.
5. **Create and populate `.env`** as described in the local quickstart.
6. **Build and orchestrate the platform**:
   ```bash
   sudo docker-compose up --build -d
   ```

---

## Health Monitoring & API Endpoints

Once running, the monitoring service exposes:
* **`GET /health`**: Returns JSON details checking Postgres connection, Redis status, active Celery worker count, and Playwright verification.
* **`GET /status`**: Returns lead database statistics (total, hot, warm, skipped leads count, active schedule campaigns count).
* **`GET /workers`**: Returns active worker nodes names and list of currently running Celery tasks.

---

## Bot Interaction Command Reference

Interact with the bot using these commands:
* **`/find [count] [industry] [location] [filters]`** — Registers a background search. Instantly returns a `job_id` and enqueues a Celery task. Results are delivered directly to the chat once scraping completes.
* **`/status`** — Displays database statistics and active search metrics.
* **`/schedule [daily/weekly/monthly] [count] [industry] [location]`** — Configures a recurring campaign (e.g., runs every day at 8 AM, or every Monday).
* **`/campaigns`** — Lists active schedule configurations.
* **`/pause [id]` / `/resume [id]`** — Pauses or resumes campaigns.
* **`/export [industry] [location]`** — Generates and downloads a spreadsheet from historical data matching the industry/location.
* **`/filter [criteria]`** — Runs an instant custom query on existing database leads and downloads the spreadsheet.

*NLP support*: Alternatively, you can talk to the bot in plain English. For example, sending:
`"give me 20 qualified dentists in Chennai"` will trigger a background `/find` task automatically.
