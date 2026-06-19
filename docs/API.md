# Reference: REST API, Bot Commands, and Configuration

This document provides technical reference details for the ERLI.PL Price Tracker API endpoints, Telegram bot commands, configuration parameters, and service costs.

---

## 1. REST API Reference

The service runs a FastAPI web server. By default, interactive API docs are available at `http://localhost:8000/docs` (Swagger UI).

### Endpoints

#### POST `/products`
Adds a new product URL to tracking, or returns the existing product if it is already tracked.

- **Request Body (JSON)**:
  ```json
  {
    "url": "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345",
    "name": "iPhone 15 Black" // Optional
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "id": 1,
    "url": "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345",
    "name": "iPhone 15 Black",
    "created_at": "2026-06-19T11:00:00Z"
  }
  ```

#### GET `/products`
Lists all tracked products with their latest scraped price.

- **Query Parameters**:
  - `skip` (int, default: 0): Pagination offset.
  - `limit` (int, default: 100): Pagination limit.
- **Response (200 OK)**:
  ```json
  [
    {
      "id": 1,
      "url": "https://erli.pl/produkt/smartfon-apple-iphone-15-128gb-czarny,15012345",
      "name": "iPhone 15 Black",
      "created_at": "2026-06-19T11:00:00Z",
      "latest_price": 3499.00
    }
  ]
  ```

#### GET `/products/{product_id}/history`
Retrieves price history records for a specific product, ordered by scraping timestamp descending.

- **Query Parameters**:
  - `limit` (int, default: 100): Maximum records to return.
  - `since` (datetime, optional): ISO datetime to filter results.
- **Response (200 OK)**:
  ```json
  [
    {
      "id": 12,
      "product_id": 1,
      "price_min": 3499.00,
      "price_max": 3599.00,
      "rating": 4.85,
      "scraped_at": "2026-06-19T12:00:00Z"
    }
  ]
  ```

#### GET `/health`
Check service health and background scheduler status.

- **Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "scheduler_running": true
  }
  ```

---

## 2. Telegram Bot Commands

The Telegram Bot interacts with users using a Finite State Machine (FSM). Below are the commands registered on the bot dispatcher:

| Command | Action | Expected User Input / Flow |
|---|---|---|
| `/start` | Starts interaction | Displays welcome message and inline keyboard menu. |
| `/help` | Explains usage | Sends a list of commands and general usage tips. |
| `/add` | Triggers FSM flow | Enters state to wait for an `erli.pl` URL. |
| `/list` | Shows tracked items | Lists all products with their latest price and "Delete" or "History" inline buttons. |

---

## 3. Configuration Reference

All settings are configured using environment variables or a `.env` file, loaded via Pydantic Settings.

| Environment Variable | Type | Default Value | Description |
|---|---|---|---|
| `DATABASE_URL` | String | *Required* | SQLAlchemy async database connection string. |
| `SERPER_API_KEY` | String | *Required* | API key for page scraping. |
| `TELEGRAM_BOT_TOKEN` | String | *Required* | Telegram bot authentication token. |
| `TELEGRAM_CHAT_ID` | String | *Required* | Target chat/user ID for price alerts. |
| `OPENAI_API_KEY` | String | *Optional* | API key for primary LLM parser. |
| `OPENAI_MODEL` | String | `gpt-4o-mini` | OpenAI model identifier. |
| `OPENAI_TIMEOUT_SECONDS` | Int | `30` | Request timeout before triggering fallback. |
| `ANTHROPIC_API_KEY` | String | *Optional* | API key for fallback LLM parser. |
| `ANTHROPIC_MODEL` | String | `claude-3-5-sonnet-20241022` | Fallback model identifier. |
| `ANTHROPIC_TIMEOUT_SECONDS`| Int | `45` | Request timeout for Anthropic fallback. |
| `SCRAPE_INTERVAL_HOURS` | Int | `12` | Hours between scheduled scraping jobs. |
| `PRICE_CHANGE_THRESHOLD_PERCENT`| Float | `5.0` | Price delta percentage required to trigger alert. |
| `ALERT_LANGUAGE` | String | `uk` | Alert translation code (`uk` or `en`). |
| `AI_ROUTER_CIRCUIT_BREAKER_THRESHOLD` | Int | `3` | Number of failures before OpenAI is skipped. |
| `AI_ROUTER_CIRCUIT_BREAKER_RESET_SECONDS` | Int | `60` | Duration to hold circuit open before retry. |

---

## 4. Serper.dev Cost Model

Scraping dynamic storefront websites consumes credits. Below is the cost breakdown based on the Serper Scraping API pricing tier:

| Plan | Price | Monthly Credits | Capacity |
|---|---|---|---|
| **Free** | $0 | 2,500 | ~40 products at 1 scrape per day |
| **Starter** | $50 / mo | 50,000 | ~8,300 scrapes per month |
| **Standard** | $150 / mo | 250,000 | ~41,600 scrapes per month |

> [!NOTE]
> Each `erli.pl` page request uses approximately **6 credits**. 
> Running 100 products at a 4-hour scrape interval consumes `100 * 6 * (24/4) * 30 = 108,000` credits/month, requiring the **Standard** plan.
