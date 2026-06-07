"""Data models for QQ group messages and queries."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GroupMessage(BaseModel):
    """A message from a QQ group chat."""

    message_id: int = Field(description="OneBot message ID")
    group_id: int = Field(description="Group ID")
    group_name: str = Field(description="Group name")
    user_id: int = Field(description="Sender QQ number")
    user_nickname: str = Field(description="Sender nickname")
    message: str = Field(description="Message content")
    timestamp: datetime = Field(description="Message timestamp")


class PrivateMessage(BaseModel):
    """A private message sent to the bot."""

    message_id: int = Field(description="OneBot message ID")
    user_id: int = Field(description="Sender QQ number")
    user_nickname: str = Field(description="Sender nickname")
    message: str = Field(description="Message content")
    timestamp: datetime = Field(description="Message timestamp")


class Interest(BaseModel):
    """A user-defined topic of interest."""

    id: int | None = Field(default=None, description="Database ID")
    user_id: int = Field(description="User QQ number")
    keyword: str = Field(description="Keyword or phrase to monitor")
    description: str = Field(description="Human-readable description")
    created_at: datetime = Field(default_factory=datetime.now)
    active: bool = Field(default=True, description="Whether this interest is active")


class QueryResult(BaseModel):
    """Result of a query with LLM summary and sources."""

    summary: str = Field(description="LLM-generated summary")
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of source messages with metadata"
    )
