"""Tests for the DigestScheduler."""

import asyncio
from datetime import datetime

import pytest

from qq_group_filter.persistence import MessageStore
from qq_group_filter.models import GroupMessage
from qq_group_filter.query import QueryHandler
from qq_group_filter.scheduler import DigestScheduler


class FakeLLM:
    async def chat_completion(self, messages, **kw):
        return "LLM摘要"


class FakeClient:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_private_message(self, user_id, message):
        self.sent.append({"user_id": user_id, "message": message})


@pytest.fixture
async def store():
    s = MessageStore(":memory:")
    await s.init_db()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_push_all_sends_digest_to_users_with_interests(store):
    """_push_all should send a digest to every user with active interests."""
    # Seed two users with interests
    await store.add_interest(1001, "GPU", "GPU相关")
    await store.add_interest(2002, "实习", "实习相关")

    # Seed a matching message for user 1001
    await store.save_group_message(GroupMessage(
        message_id=1,
        group_id=111,
        group_name="技术群",
        user_id=9999,
        user_nickname="张三",
        message="GPU降价了",
        timestamp=datetime.now(),
    ))

    fake_client = FakeClient()
    handler = QueryHandler(store, FakeLLM())
    scheduler = DigestScheduler(handler, store, fake_client, digest_hour=8)

    await scheduler._push_all()

    # User 1001 has matching messages → should receive digest
    sent_to_1001 = [m for m in fake_client.sent if m["user_id"] == 1001]
    assert len(sent_to_1001) == 1
    assert "GPU" in sent_to_1001[0]["message"]

    # User 2002 has NO matching messages → "没有" in digest → not sent
    sent_to_2002 = [m for m in fake_client.sent if m["user_id"] == 2002]
    assert len(sent_to_2002) == 0


@pytest.mark.asyncio
async def test_get_users_with_interests(store):
    """get_users_with_interests returns distinct user_ids."""
    await store.add_interest(1001, "a", "")
    await store.add_interest(1001, "b", "")
    await store.add_interest(2002, "c", "")

    users = await store.get_users_with_interests()
    assert set(users) == {1001, 2002}


@pytest.mark.asyncio
async def test_scheduler_disabled_when_hour_negative():
    """Setting digest_hour=-1 means start() does not launch a background task."""
    scheduler = DigestScheduler(None, None, None, digest_hour=-1)
    scheduler.start()
    assert scheduler._task is None


@pytest.mark.asyncio
async def test_scheduler_start_is_idempotent():
    """Repeated start() calls should not stack duplicate background tasks."""
    scheduler = DigestScheduler(None, None, None, digest_hour=3)

    scheduler.start()
    first_task = scheduler._task
    scheduler.start()

    assert scheduler._task is first_task

    await scheduler.stop()


@pytest.mark.asyncio
async def test_seconds_until_next_fire():
    """Sanity check — should return a value between 0 and 86400."""
    scheduler = DigestScheduler(None, None, None, digest_hour=3)
    delay = scheduler._seconds_until_next_fire()
    assert 0 < delay <= 86400
