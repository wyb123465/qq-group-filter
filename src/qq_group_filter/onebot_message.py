"""Utilities for handling OneBot message payloads."""

from typing import Any


def onebot_message_to_text(message: Any) -> str:
    """Convert OneBot string or array message payloads into plain text."""
    if isinstance(message, str):
        return message

    if not isinstance(message, list):
        return ""

    text_parts = []
    for segment in message:
        if not isinstance(segment, dict):
            continue
        if segment.get("type") != "text":
            continue

        data = segment.get("data")
        if isinstance(data, dict):
            text = data.get("text")
            if isinstance(text, str):
                text_parts.append(text)

    return "".join(text_parts).strip()
