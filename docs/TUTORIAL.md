# Tutorial: Monitor Your First ERLI.PL Product

This tutorial guides you through setting up ERLI.PL Price Tracker from scratch, adding a product to track, and receiving your first price alert on Telegram.

**What you will build:** A local running price monitor that alerts you on Telegram when prices change on `erli.pl`.
**What you will learn:**
- How to configure and spin up the tracker locally.
- How to interact with the FSM-based Telegram bot.
- How to trigger a manual scrape and price change notification.

**Prerequisites:**
- [ ] Python 3.13+ installed.
- [ ] Docker and Docker Compose installed.
- [ ] A [Serper.dev](https://serper.dev) API Key (free tier works!).
- [ ] OpenAI and/or Anthropic API keys (for AI-powered parsing).
- [ ] A Telegram bot token (created via [@BotFather](https://t.me/BotFather)) and your Telegram Chat ID (retrieve it using [@userinfobot](https://t.me/userinfobot)).

---

## Step 1: Configure Your Environment

First, duplicate the example configuration file to create your local `.env` file.

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in your API credentials. Here is a configuration snippet explaining what you must provide:

```env
# Scraping API Key from Serper.dev
SERPER_API_KEY=your_serper_key_here

# Credentials for your Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321

# LLM Keys for page parsing
OPENAI_API_KEY=sk-proj-your_openai_key
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key
```

> [!TIP]
> If you only have one LLM key (e.g., OpenAI), the system will still function but will lack automatic fallback capability if the primary provider fails.

---

## Step 2: Spin Up the Services

Start the PostgreSQL database container. This ensures that the application has a persistent database to store product data and price history.

```bash
docker compose -f infra/docker/docker-compose.yml up -d db
```

Confirm that the database is running successfully:

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

You should see the `db` service marked as `Up`.

---

## Step 3: Run the Tracker and Telegram Bot

Run the application locally. We will use Poetry to install dependencies and run the main entry point, which starts the FastAPI REST API, the Telegram bot listener, and the background scheduler.

1. Install project dependencies:
   ```bash
   poetry install
   ```
2. Start the application:
   ```bash
   poetry run uvicorn src.main:app --reload
   ```

You should see startup logs indicating that the database pool is initialized, the scheduler is active, and the Telegram bot polling has started:

```text
[info] app_starting
[info] scheduler_started              interval_hours=12
[info] bot_starting
```

---

## Step 4: Add a Product for Tracking

Open Telegram and open a chat with your bot. 

1. Send `/start` to see the main menu.
2. Click the **Add Product** button (or type `/add`).
3. Send a valid `erli.pl` product URL, for example:
   `https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345`
4. The bot will parse the URL, check it using the scraping engine, and save it. You will see:
   `✅ Product successfully added to tracking!`

---

## Step 5: Test and Trigger a Price Alert

To verify that the entire integration chain works immediately without waiting 12 hours for the scheduled job:

1. Run the manual scraping CLI script targeting the product you just added:
   ```bash
   poetry run python scripts/manual_scrape.py --url "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345"
   ```
2. Check your Telegram bot chat. You should receive a formatted notification detailing the current price, rating, and tracking status.
3. If you want to force a **Price Alert** notification, you can temporarily edit the alert threshold to `0.0` in your `.env` file:
   ```env
   PRICE_CHANGE_THRESHOLD_PERCENT=0.0
   ```
   Restart the app and run the manual scrape script again. This will immediately trigger a price delta notification because any price check is treated as a threshold breach!

---

## Next Steps

Now that you have a functioning local tracker:
- Read the [How-To Deploy Guide](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/DEPLOYMENT.md) to set up production deployment on Railway.app.
- See the [API Reference](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/API.md) to integrate the tracking engine with external dashboards.
