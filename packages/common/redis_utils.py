"""
Redis Utilities
Helper functions dla komunikacji przez Redis Streams.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
import redis.asyncio as redis
from .schemas import StreamMessage


async def publish_message(
    redis_client: redis.Redis,
    stream_name: str,
    agent_name: str,
    data: Dict[str, Any],
    message_type: Optional[str] = None
) -> str:
    """
    Publikuj wiadomość do Redis Stream

    Args:
        redis_client: Klient Redis
        stream_name: Nazwa strumienia
        agent_name: Nazwa agenta wysyłającego
        data: Dane do wysłania
        message_type: Opcjonalny typ wiadomości

    Returns:
        Message ID z Redis
    """
    message = StreamMessage(
        agent=agent_name,
        timestamp=datetime.now().isoformat(),
        data=data,
        message_type=message_type
    )

    # Serializuj do JSON
    message_dict = {
        "agent": message.agent,
        "timestamp": message.timestamp,
        "data": json.dumps(message.data),
        "message_type": message.message_type or ""
    }

    message_id = await redis_client.xadd(stream_name, message_dict)
    return message_id


async def create_consumer_group(
    redis_client: redis.Redis,
    stream_name: str,
    group_name: str,
    start_id: str = "0"
) -> bool:
    """
    Utwórz Consumer Group jeśli nie istnieje

    Args:
        redis_client: Klient Redis
        stream_name: Nazwa strumienia
        group_name: Nazwa grupy
        start_id: ID startowe ("0" = od początku, "$" = od teraz)

    Returns:
        True jeśli utworzono, False jeśli już istniała
    """
    try:
        await redis_client.xgroup_create(
            stream_name, group_name, id=start_id, mkstream=True
        )
        return True
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            return False
        raise


def deserialize_message(message_data: Dict[str, str]) -> StreamMessage:
    """
    Deserializuj wiadomość z Redis Stream

    Args:
        message_data: Surowe dane z Redis

    Returns:
        StreamMessage object
    """
    data = json.loads(message_data.get("data", "{}"))

    return StreamMessage(
        agent=message_data.get("agent", "unknown"),
        timestamp=message_data.get("timestamp", datetime.now().isoformat()),
        data=data,
        message_type=message_data.get("message_type")
    )
