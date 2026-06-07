"""Tests for OneBot WebSocket client behavior."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from qq_group_filter.onebot_client import OneBotClient


@pytest.mark.asyncio
async def test_connect_uses_websockets_16_header_parameter(monkeypatch):
    """websockets 16 expects additional_headers, not extra_headers."""
    captured = {}

    async def fake_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return AsyncMock()

    monkeypatch.setattr("websockets.connect", fake_connect)

    client = OneBotClient("ws://localhost:3001", "secret-token")
    await client.connect()

    assert captured["url"] == "ws://localhost:3001"
    assert captured["kwargs"]["additional_headers"] == {
        "Authorization": "Bearer secret-token"
    }
    assert "extra_headers" not in captured["kwargs"]


@pytest.mark.asyncio
async def test_call_action_matches_response_by_echo():
    """call_action attaches an echo and resolves when the matching response arrives."""
    client = OneBotClient("ws://localhost:3001")

    sent_payloads = []

    async def fake_send(raw):
        sent_payloads.append(json.loads(raw))

    fake_ws = AsyncMock()
    fake_ws.send = fake_send
    client.ws = fake_ws

    # Kick off call_action. It awaits the response Future.
    task = asyncio.create_task(client.call_action("get_group_list"))
    # Yield so the send completes and the echo is registered.
    await asyncio.sleep(0)

    assert len(sent_payloads) == 1
    echo = sent_payloads[0]["echo"]
    assert sent_payloads[0]["action"] == "get_group_list"

    # Simulate the server's response coming back through _dispatch_event.
    await client._dispatch_event({
        "echo": echo,
        "status": "ok",
        "retcode": 0,
        "data": [{"group_id": 111, "group_name": "技术群"}],
    })

    response = await task
    assert response["data"][0]["group_name"] == "技术群"


@pytest.mark.asyncio
async def test_refresh_group_list_populates_cache(monkeypatch):
    """After refresh_group_list, get_group_name returns cached names without an API call."""
    client = OneBotClient("ws://localhost:3001")

    async def fake_call_action(action, params=None, timeout=10.0):
        assert action == "get_group_list"
        return {
            "status": "ok",
            "retcode": 0,
            "data": [
                {"group_id": 111, "group_name": "技术群"},
                {"group_id": 222, "group_name": "求职群"},
                {"group_id": 333},                          # missing name → skipped
                "not-a-dict",                               # malformed → skipped
            ],
        }

    monkeypatch.setattr(client, "call_action", fake_call_action)

    await client.refresh_group_list()

    assert client._group_name_cache == {111: "技术群", 222: "求职群"}
    # Cached lookups never call the API.
    assert await client.get_group_name(111) == "技术群"


@pytest.mark.asyncio
async def test_get_group_name_falls_back_to_id_on_failure(monkeypatch):
    """If get_group_info fails, get_group_name returns str(group_id) — never crashes the caller."""
    client = OneBotClient("ws://localhost:3001")

    async def failing_call_action(action, params=None, timeout=10.0):
        raise RuntimeError("API unreachable")

    monkeypatch.setattr(client, "call_action", failing_call_action)

    name = await client.get_group_name(987654321)
    assert name == "987654321"


@pytest.mark.asyncio
async def test_listen_forever_starts_listener_before_on_connected_actions(monkeypatch):
    """on_connected actions need listen() running so echo responses can resolve."""

    class FakeWebSocket:
        def __init__(self):
            self.incoming = asyncio.Queue()
            self.closed = False

        async def send(self, raw):
            payload = json.loads(raw)
            if payload["action"] == "get_group_list":
                await self.incoming.put(json.dumps({
                    "echo": payload["echo"],
                    "status": "ok",
                    "retcode": 0,
                    "data": [{"group_id": 111, "group_name": "技术群"}],
                }))

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.closed:
                raise StopAsyncIteration
            raw = await self.incoming.get()
            if raw is None:
                raise StopAsyncIteration
            return raw

        async def close(self):
            self.closed = True
            await self.incoming.put(None)

    fake_ws = FakeWebSocket()

    async def fake_connect(url, **kwargs):
        return fake_ws

    monkeypatch.setattr("websockets.connect", fake_connect)

    client = OneBotClient("ws://localhost:3001")

    async def on_connected():
        await client.refresh_group_list()
        await client.close()

    await asyncio.wait_for(
        client.listen_forever(on_connected=on_connected),
        timeout=1.0,
    )

    assert client._group_name_cache == {111: "技术群"}
