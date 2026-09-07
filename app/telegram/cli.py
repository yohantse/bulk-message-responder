import argparse
import asyncio
import json
import sys

import httpx

from app.config.settings import get_settings


async def set_webhook(url: str, secret_token: str | None = None) -> None:
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured.")
        sys.exit(1)

    secret = secret_token or settings.telegram_webhook_secret
    endpoint = f"https://api.telegram.org/bot{token}/setWebhook"
    payload: dict[str, str] = {"url": url}
    if secret:
        payload["secret_token"] = secret

    async with httpx.AsyncClient() as client:
        res = await client.post(endpoint, json=payload)
        print(f"Status: {res.status_code}")
        print(json.dumps(res.json(), indent=2))


async def get_webhook_info() -> None:
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured.")
        sys.exit(1)

    endpoint = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    async with httpx.AsyncClient() as client:
        res = await client.get(endpoint)
        print(f"Status: {res.status_code}")
        print(json.dumps(res.json(), indent=2))


async def delete_webhook() -> None:
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured.")
        sys.exit(1)

    endpoint = f"https://api.telegram.org/bot{token}/deleteWebhook"
    async with httpx.AsyncClient() as client:
        res = await client.post(endpoint)
        print(f"Status: {res.status_code}")
        print(json.dumps(res.json(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram Webhook Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set-webhook", help="Register a webhook URL with Telegram")
    set_parser.add_argument(
        "url", help="Public HTTPS URL for the webhook (e.g. https://your-domain/webhooks/telegram)"
    )
    set_parser.add_argument(
        "--secret", help="Optional secret token (defaults to TELEGRAM_WEBHOOK_SECRET)", default=None
    )

    subparsers.add_parser("get-webhook-info", help="Get current Telegram webhook status")
    subparsers.add_parser("delete-webhook", help="Delete the current webhook")

    args = parser.parse_args()

    if args.command == "set-webhook":
        asyncio.run(set_webhook(args.url, args.secret))
    elif args.command == "get-webhook-info":
        asyncio.run(get_webhook_info())
    elif args.command == "delete-webhook":
        asyncio.run(delete_webhook())


if __name__ == "__main__":
    main()
