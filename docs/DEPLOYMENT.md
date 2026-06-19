# How-To Guide: Deploying and Monitoring in Production

This guide walks you through deploying the ERLI.PL Price Tracker to production on Railway.app, setting up persistent storage, and configuring error tracking and monitoring.

---

## 1. Deploying to Railway.app

Railway.app is the recommended cloud platform for this service as it supports multi-stage Docker builds out-of-the-box and provides native PostgreSQL integration.

### Step 1: Provision a PostgreSQL Instance on Railway

Before deploying the application code, you need a running database instance:

1. Log in to your [Railway.app Console](https://railway.app/).
2. Click **New Project** and select **Provision PostgreSQL**.
3. Once the database container is created, navigate to the **Variables** tab of the PostgreSQL service and copy the `DATABASE_URL` (usually starts with `postgresql://`).

### Step 2: Create the Application Service

Deploy the tracker from your git repository:

1. Click **New** -> **GitHub Repo** and select your repository.
2. Railway will automatically detect the `infra/docker/Dockerfile` and start a build.
3. **IMPORTANT**: Do not let it start the application yet, as you must configure environment variables first.

### Step 3: Configure Environment Variables

Navigate to the **Variables** tab of your new application service and add the following:

| Variable | Value | Source / Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Binds directly to the Railway database service. |
| `SERPER_API_KEY` | `your_serper_key` | Obtained from Serper.dev console. |
| `TELEGRAM_BOT_TOKEN` | `your_bot_token` | Obtained from @BotFather. |
| `TELEGRAM_CHAT_ID` | `your_chat_id` | Obtained from @userinfobot. |
| `OPENAI_API_KEY` | `your_openai_key` | Obtained from OpenAI dashboard. |
| `ANTHROPIC_API_KEY` | `your_anthropic_key` | Obtained from Anthropic dashboard. |
| `SCRAPE_INTERVAL_HOURS` | `4` | We recommend 4 hours for production tracking. |
| `PRICE_CHANGE_THRESHOLD_PERCENT` | `5.0` | Alert threshold. |
| `ALERT_LANGUAGE` | `uk` | Use `uk` for Ukrainian notifications or `en` for English. |

Railway will automatically rebuild and deploy the application once these environment variables are set.

---

## 2. Configuring Production Monitoring

To ensure production reliability and catch bugs before users notice them, configure Sentry and Uptime Robot.

### Error Tracking with Sentry

We have built-in Sentry integration. Sentry captures all unhandled exceptions, database connection pool issues, and AI router failovers.

1. Go to [Sentry.io](https://sentry.io/) and create a new project (select Python/FastAPI).
2. Copy your Sentry DSN URL.
3. Add the following environment variable to your Railway service configuration:
   ```env
   SENTRY_DSN=https://your-dsn-url@sentry.io/project-id
   ```
4. Sentry will now automatically capture and log errors like `AIRouterError` or `SerperAPIError`.

### Availability Monitoring with Uptime Robot

FastAPI exposes a `/health` endpoint that checks if the scheduler and database are functional.

1. Locate the public domain assigned by Railway to your application service (e.g. `https://your-app-production.up.railway.app`).
2. Go to [Uptime Robot](https://uptimerobot.com/) and click **Add New Monitor**.
3. Configure the monitor:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: ERLI.PL Price Tracker Health
   - **URL (or IP)**: `https://your-app-production.up.railway.app/health`
   - **Monitoring Interval**: Every 5 minutes
4. Uptime Robot will alert you via email or Slack if the service goes down or returns a non-200 response status.

---

## 3. Production CLI Operations

If you need to perform manual tasks, run scripts, or seed data inside the production container, use the Railway CLI or the Railway Web Terminal.

### Seeding Products from CSV

To seed your initial list of products:

1. Upload your `products.csv` to the server or create it via CLI.
2. Run the seeding script inside the container environment:
   ```bash
   poetry run python scripts/seed_products.py --file products.csv
   ```

### Manual Scrape Check

To force scrape a specific URL and test notifications:

```bash
poetry run python scripts/manual_scrape.py --url "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345"
```
