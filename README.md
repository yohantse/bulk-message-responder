# Telegram Conversation Platform

The Telegram communication foundation for an AI-powered high-volume customer communication platform.

Built with **Python 3.12+**, **FastAPI**, **SQLAlchemy 2.x (async)**, **Alembic**, and **PostgreSQL 16+**.

---

## 1. Architectural Principles

1. **Telegram is a Transport Mechanism**: Telegram-specific data structures are normalized at the edge. The core application logic operates entirely on internal domain models (`IncomingMessage`, `User`, `Conversation`, `Message`) behind a generic `ChannelAdapter` protocol. This allows future channels (WhatsApp, Instagram, etc.) without altering business logic or database schemas.
2. **Modular Monolith**: Logical modules are cleanly isolated (`telegram/`, `domain/`, `services/`, `repositories/`, `database/`, `api/`).
3. **Decoupled 3-Phase Execution**: External network calls (Telegram Bot API) never hold open a PostgreSQL database transaction. Processing is decoupled into:
   - **Phase 1**: Ingest incoming message, resolve user/conversation, commit DB transaction.
   - **Phase 2**: Dispatch response via external channel adapter outside any DB transaction.
   - **Phase 3**: Persist outgoing message and send status in a separate DB transaction.
4. **Authoritative Idempotency & Chat-Scoped Uniqueness**: Message uniqueness is strictly scoped to chats via `(channel, external_chat_id, external_message_id, direction)`. Concurrent duplicate deliveries hitting database unique constraints are caught gracefully and return HTTP 200 without raising server errors.
5. **Resilient & Safe**: Unhandled or unsupported updates (media, group chats, callback queries) return HTTP 200 without crashing or prompting endless webhook retries. Secrets and customer message contents are never indiscriminately logged.

---

## 2. Architecture Overview

```text
                        Telegram
                           |
                           | HTTPS Webhook
                           v
                 +-------------------+
                 | Telegram Gateway  |
                 | Webhook Handler   |
                 | Update Parser     |
                 +---------+---------+
                           | Normalized IncomingMessage
                           v
                 +-------------------+
                 | Message Service   |
                 | Idempotency Check |
                 | User / Chat Svc   |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | PostgreSQL        |
                 | Users             |
                 | Conversations     |
                 | Messages          |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 | Telegram Sender   |
                 | (ChannelAdapter)  |
                 +---------+---------+
                           |
                           v
                        Telegram
```

---

## 3. Project Structure

```text
telegram-platform/
├── app/
│   ├── main.py                    # FastAPI application & health check
│   ├── config/                    # Pydantic Settings & environment
│   ├── api/webhooks/              # Webhook endpoints (POST /webhooks/telegram)
│   ├── telegram/                  # Isolated Telegram transport (Parser, Sender, CLI)
│   ├── domain/                    # Internal normalized models (IncomingMessage, etc.)
│   ├── services/                  # MessageService, UserService, ConversationService
│   ├── repositories/              # Database persistence layer
│   ├── database/                  # SQLAlchemy Base, async session, models
│   ├── schemas/                   # Pydantic serialization schemas
│   └── utils/                     # Structured JSON logging with secret masking
├── migrations/                    # Alembic async migration environment & versions
├── tests/
│   ├── conftest.py                # Pytest fixtures, in-memory SQLite, mock adapter
│   ├── unit/                      # Parser and service unit tests
│   └── integration/               # Webhook HTTP & idempotency integration tests
├── Dockerfile                     # Production-ready Python 3.13-slim image
├── docker-compose.yml             # Local dev setup with PostgreSQL & FastAPI
├── alembic.ini                    # Alembic configuration
├── pyproject.toml                 # Dependencies and tool configurations
└── .env.example                   # Environment variable template
```

---

## 4. Quickstart & Local Development

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (Python 3.13 supported)

### Step 1: Clone and Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your Telegram credentials:
```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/telegram_platform
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_WEBHOOK_SECRET=your_secure_random_secret_token
LOG_LEVEL=INFO
```

### Step 2: Start with Docker Compose
```bash
docker compose up --build
```
This will:
1. Start PostgreSQL 16 on port `5432` with automated health checks.
2. Run Alembic database migrations (`alembic upgrade head`).
3. Start the FastAPI application with live-reload on `http://localhost:8000`.

### Step 3: Verify Health Endpoint
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## 5. Webhook Management CLI

Use the built-in CLI to manage Telegram webhooks without exposing administrative HTTP endpoints:

```bash
# Register webhook with Telegram (includes secret token verification header)
python -m app.telegram.cli set-webhook https://your-public-domain.com/webhooks/telegram

# Inspect current webhook status
python -m app.telegram.cli get-webhook-info

# Delete webhook
python -m app.telegram.cli delete-webhook
```

---

## 6. Running Tests Locally

Create a virtual environment and install test dependencies:
```bash
python -m venv .venv
.\.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -e ".[dev]"
pytest -v
```

### Test Coverage Highlights:
- **Parser Unit Tests**: Verifies valid text messages with `update_id` preservation, rejects non-private chats (groups/supergroups), gracefully ignores non-text media (photos/stickers), callback queries, and whitespace-only text.
- **Service Unit Tests**: Validates user and conversation creation/reuse, automated response generation (`/start` and general queries), pre-check idempotency, chat-scoped message uniqueness across distinct chats, database-level race condition idempotency (`IntegrityError` recovery), and phase isolation when Telegram send fails.
- **Integration Tests**: Tests secret verification (403 on missing/invalid secrets), unsupported update handling (200 OK), end-to-end webhook persistence with `external_chat_id`, and duplicate update prevention (200 OK without duplication).

---

## 7. Database Migrations

Apply migrations to your configured database:
```bash
alembic upgrade head
```

Create a new migration after model changes:
```bash
alembic revision --autogenerate -m "describe change"
```
