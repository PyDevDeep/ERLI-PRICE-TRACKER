# ERLI.PL Price Tracker 🛒📉

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://aiogram.dev/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

An automated price monitoring service for ERLI.PL with instant Telegram notifications, dynamic AI-powered fallback parsing, and a full REST API.

---

## Why This Exists

E-commerce websites frequently update their page structures, breaking static web scrapers and regular expression parsers. ERLI.PL Price Tracker solves this by combining high-performance API scraping (via Serper.dev) with a hybrid parsing pipeline: it tries optimized local JSON-LD regex extraction first, then automatically routes complex or updated page structures to a dual-LLM fallback router (OpenAI `gpt-4o-mini` → Anthropic `claude-3-5-sonnet`) equipped with a circuit breaker. This ensures you receive consistent, real-time price alerts on Telegram without manual script maintenance.

---

## Quick Start

Get the tracker running locally and perform a manual price check in under a minute.

```bash
# 1. Clone the repository and configure environment variables
git clone https://github.com/your-username/erli-price-tracker.git
cd erli-price-tracker
cp .env.example .env

# 2. Spin up the local database
docker compose -f infra/docker/docker-compose.yml up -d db

# 3. Install dependencies and run tests
poetry install
poetry run pytest
```

---

## Installation

Ensure your local development environment meets the requirements below before setting up the application.

### Prerequisites
- Python 3.13+ installed
- Docker and Docker Compose installed
- A [Serper.dev](https://serper.dev) API Key
- A Telegram Bot Token and Chat ID (created via [@BotFather](https://t.me/BotFather))
- OpenAI and/or Anthropic API keys (for AI fallback parsing)

### Setup Steps

1. Create a local configuration file:
   ```bash
   cp .env.example .env
   ```
2. Populate the `.env` file with your credentials:
   ```env
   SERPER_API_KEY=your_serper_key
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/price_tracker
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   OPENAI_API_KEY=your_openai_key
   ANTHROPIC_API_KEY=your_anthropic_key
   ```
3. Run the development database:
   ```bash
   docker compose -f infra/docker/docker-compose.yml up -d db
   ```
4. Install Python packages and launch the services:
   ```bash
   poetry install
   poetry run uvicorn src.main:app --reload
   ```

---

## Usage

Interact with the price tracker using the CLI scripts, the REST API, or the Telegram Bot UI.

### 1. Manual Scrape via CLI
Test the scraper immediately by running a manual price extraction script on a product URL:
```bash
poetry run python scripts/manual_scrape.py --url "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345"
```

### 2. REST API Integration
Register new tracking targets or retrieve price histories programmatically.
```bash
# Add a new product to tracking
curl -X POST http://localhost:8000/products \
     -H "Content-Type: application/json" \
     -d '{"url": "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345", "name": "iPhone 15"}'

# Fetch all products with their latest price
curl -X GET http://localhost:8000/products
```

### 3. Telegram Bot Interactions
Open a direct chat with your Telegram Bot and manage tracking interactively:
- Send `/start` to see the main control panel.
- Send `/add` and enter an ERLI.PL URL to start tracking a product.
- Send `/list` to inspect your tracked items, view price charts, or stop tracking.

---

## Documentation Map (Divio System)

- [Project Documentation Folder](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs)

| File Path | Documentation Type | Description |
| :--- | :--- | :--- |
| 🎓 **[docs/TUTORIAL.md](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/TUTORIAL.md)** | Tutorial | A step-by-step guide to configure, run, and trigger your first price change alert. |
| 🛠️ **[docs/DEPLOYMENT.md](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/DEPLOYMENT.md)** | How-To Guide | Production deployment instructions for Railway.app, Sentry error logging, and Uptime Robot. |
| 📋 **[docs/API.md](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/API.md)** | Reference | Environment variables schema, REST API specs, bot commands list, and Serper cost model. |
| 🧠 **[docs/ARCHITECTURE.md](file:///C:/AI/ERLIPL_PRICE_TRACKE/docs/ARCHITECTURE.md)** | Explanation | Architectural design decisions, AI Router fallback, circuit breaker states, and risk mitigations. |
