"""Integration tests for bot event handling."""

import asyncio
import json
import time

import pytest

from qq_group_filter.persistence import MessageStore
from qq_group_filter.llm_provider import LLMProvider
from qq_group_filter.onebot_client import OneBotClient
from qq_group_filter.onebot_message import onebot_message_to_text
from qq_group_filter.query import QueryHandler
from qq_group_filter.models import GroupMessage
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeOneBotClient:
    """A thin fake that captures sent messages instead of using a WebSocket."""

    def __init__(self):
        self.sent_messages: list[dict] = []
        self._group_name_cache = {111: "技术群", 222: "求职群"}

    async def send_private_message(self, user_id: int, message: str):
        self.sent_messages.append({"user_id": user_id, "message": message})

    async def get_group_name(self, group_id: int) -> str:
        return self._group_name_cache.get(group_id, str(group_id))


class FakeLLM:
    """A fake LLM that returns a predictable summary."""

    def __init__(self, response: str = "这是LLM总结"):
        self.response = response
        self.calls: list[list[dict]] = []

    async def chat_completion(self, messages, **kwargs):
        self.calls.append(messages)
        return self.response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def store():
    s = MessageStore(":memory:")
    await s.init_db()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_group_message_stored_correctly(store):
    """Simulate a group message event → verify it is persisted."""
    client = FakeOneBotClient()
    now = int(time.time())

    event = {
        "post_type": "message",
        "message_type": "group",
        "message_id": 1001,
        "group_id": 111,
        "user_id": 9001,
        "message": "AutoDL 3090 降价了",
        "sender": {"user_id": 9001, "nickname": "张三"},
        "time": now,
    }

    # Simulate what bot.py's handle_group_message does:
    message_text = onebot_message_to_text(event.get("message"))
    group_name = await client.get_group_name(event["group_id"])

    msg = GroupMessage(
        message_id=event["message_id"],
        group_id=event["group_id"],
        group_name=group_name,
        user_id=event["sender"]["user_id"],
        user_nickname=event["sender"]["nickname"],
        message=message_text,
        timestamp=datetime.fromtimestamp(event["time"]),
    )
    await store.save_group_message(msg)

    # Verify
    results = await store.search_messages("AutoDL")
    assert len(results) == 1
    assert results[0].group_name == "技术群"
    assert results[0].user_nickname == "张三"


@pytest.mark.asyncio
async def test_private_query_returns_summary(store):
    """Simulate: some group messages exist → user asks a question → gets summary."""
    # Seed messages
    now = datetime.now()
    for i in range(3):
        await store.save_group_message(GroupMessage(
            message_id=2000 + i,
            group_id=111,
            group_name="技术群",
            user_id=9001 + i,
            user_nickname=f"用户{i}",
            message=f"GPU 租赁方案{i}: AutoDL 很便宜",
            timestamp=now,
        ))

    fake_llm = FakeLLM(response="最近有3条关于GPU租赁的讨论")
    handler = QueryHandler(store, fake_llm)

    result = await handler.handle_query(user_id=12345, query_text="最近群里有讨论GPU租赁吗")

    assert "GPU租赁" in result.summary
    assert len(result.sources) == 3
    assert fake_llm.calls  # LLM was called


@pytest.mark.asyncio
async def test_private_query_no_results(store):
    """When nothing matches, the bot returns a "no results" message."""
    fake_llm = FakeLLM()
    handler = QueryHandler(store, fake_llm)

    result = await handler.handle_query(user_id=12345, query_text="有没有讨论量子计算")

    assert "未找到" in result.summary
    assert result.sources == []
    assert not fake_llm.calls  # LLM was NOT called


@pytest.mark.asyncio
async def test_help_command(store):
    """The /help command returns help text without touching the LLM."""
    client = FakeOneBotClient()

    # Simulate the routing logic from bot.py
    text = "/help"
    if text.startswith("/help"):
        from qq_group_filter.bot import HELP_TEXT
        await client.send_private_message(12345, HELP_TEXT)

    assert len(client.sent_messages) == 1
    assert "使用方法" in client.sent_messages[0]["message"]


@pytest.mark.asyncio
async def test_interests_add_and_digest(store):
    """Add an interest → seed matching messages → /digest returns a useful summary."""
    user_id = 12345

    # Add interest
    await store.add_interest(user_id, "GPU", "关注GPU相关信息")

    # Seed a matching message
    await store.save_group_message(GroupMessage(
        message_id=3001,
        group_id=222,
        group_name="求职群",
        user_id=9999,
        user_nickname="李四",
        message="GPU服务器降价了，推荐大家看看",
        timestamp=datetime.now(),
    ))

    fake_llm = FakeLLM()
    handler = QueryHandler(store, fake_llm)

    digest = await handler.generate_daily_digest(user_id)

    assert "GPU" in digest
    assert "1条新消息" in digest
    assert "李四" in digest


@pytest.mark.asyncio
async def test_array_message_event_stored(store):
    """OneBot array-format messages are correctly extracted and stored."""
    client = FakeOneBotClient()

    event = {
        "post_type": "message",
        "message_type": "group",
        "message_id": 4001,
        "group_id": 111,
        "user_id": 9001,
        "message": [
            {"type": "text", "data": {"text": "实习机会："}},
            {"type": "image", "data": {"url": "http://example.com/img.jpg"}},
            {"type": "text", "data": {"text": "字节跳动前端实习"}},
        ],
        "sender": {"user_id": 9001, "nickname": "王五"},
        "time": int(time.time()),
    }

    message_text = onebot_message_to_text(event.get("message"))
    assert message_text == "实习机会：字节跳动前端实习"

    group_name = await client.get_group_name(event["group_id"])
    msg = GroupMessage(
        message_id=event["message_id"],
        group_id=event["group_id"],
        group_name=group_name,
        user_id=event["sender"]["user_id"],
        user_nickname=event["sender"]["nickname"],
        message=message_text,
        timestamp=datetime.fromtimestamp(event["time"]),
    )
    await store.save_group_message(msg)

    results = await store.search_messages("字节跳动")
    assert len(results) == 1
    assert results[0].message == "实习机会：字节跳动前端实习"
