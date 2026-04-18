import aiohttp
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_push_notifications(tokens: list[str], title: str, body: str, data: dict | None = None):
    if not tokens:
        return

    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
        }
        for token in tokens
    ]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.EXPO_PUSH_URL,
                json=messages,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                result = await resp.json()
                logger.info("Push sent to %d tokens: %s", len(tokens), result)
    except Exception as e:
        logger.error("Push notification error: %s", e)
