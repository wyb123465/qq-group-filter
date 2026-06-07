"""OneBot v11 WebSocket client."""

import asyncio
import contextlib
import json
import logging
import uuid
from typing import Any, Callable

import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)

# Reconnect backoff schedule (seconds). Stops growing past the last value.
_RECONNECT_BACKOFF = (5, 10, 20, 40, 60)


class OneBotClient:
    """OneBot v11 WebSocket client for QQ bot communication."""

    def __init__(self, ws_url: str, access_token: str = ""):
        """
        Initialize OneBot client.

        Args:
            ws_url: WebSocket server URL (e.g., ws://localhost:3001)
            access_token: Optional access token for authentication
        """
        self.ws_url = ws_url
        self.access_token = access_token
        self.ws = None
        self._handlers: dict[str, list[Callable[[dict], Any]]] = {
            "group_message": [],
            "private_message": [],
        }
        self._running = False
        self._stop_event = asyncio.Event()

        # echo → Future, for matching action responses to their requests.
        self._pending_responses: dict[str, asyncio.Future] = {}

        # Cached group_id → group_name. Filled lazily via get_group_info,
        # bulk-populated on connect via get_group_list.
        self._group_name_cache: dict[int, str] = {}

    # ------------------------------------------------------------------ #
    # Handler registration                                               #
    # ------------------------------------------------------------------ #

    def on_group_message(self, handler: Callable[[dict], Any]):
        """Register a handler for group messages."""
        self._handlers["group_message"].append(handler)

    def on_private_message(self, handler: Callable[[dict], Any]):
        """Register a handler for private messages."""
        self._handlers["private_message"].append(handler)

    # ------------------------------------------------------------------ #
    # Connection lifecycle                                               #
    # ------------------------------------------------------------------ #

    async def connect(self):
        """Establish WebSocket connection (single attempt)."""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        self.ws = await websockets.connect(self.ws_url, additional_headers=headers)
        logger.info(f"Connected to OneBot server: {self.ws_url}")

    async def listen(self):
        """Listen for events from the OneBot server (single connection)."""
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")

        self._running = True
        logger.info("Started listening for events")

        try:
            async for raw in self.ws:
                try:
                    event = json.loads(raw)
                    await self._dispatch_event(event)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {raw!r}")
                except Exception as e:
                    logger.error(f"Error handling event: {e}", exc_info=True)
        except WebSocketException as e:
            logger.warning(f"WebSocket closed: {e}")
            raise
        finally:
            self._running = False

    async def listen_forever(self, on_connected: Callable[[], Any] | None = None):
        """
        Connect and listen with automatic reconnect on disconnect.

        Implements NFR-2.2 from the spec: exponential backoff
        (5s → 10s → 20s → 40s → 60s, then steady at 60s).

        Args:
            on_connected: Optional async callback fired after each
                          successful (re)connection — use it to bootstrap
                          per-session state like the group_name cache.
        """
        backoff_idx = 0
        while not self._stop_event.is_set():
            try:
                await self.connect()
                backoff_idx = 0  # Reset on successful connect.
                listen_task = asyncio.create_task(self.listen())

                try:
                    if on_connected is not None:
                        try:
                            if asyncio.iscoroutinefunction(on_connected):
                                await on_connected()
                            else:
                                on_connected()
                        except Exception as e:
                            logger.error(f"on_connected callback failed: {e}", exc_info=True)

                    await listen_task
                finally:
                    if not listen_task.done():
                        listen_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await listen_task
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if self._stop_event.is_set():
                break

            delay = _RECONNECT_BACKOFF[min(backoff_idx, len(_RECONNECT_BACKOFF) - 1)]
            backoff_idx += 1
            logger.info(f"Reconnecting in {delay}s...")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                break  # stop_event was set during the wait → exit cleanly
            except asyncio.TimeoutError:
                pass  # Timeout reached → loop and reconnect.

    # ------------------------------------------------------------------ #
    # Event dispatch                                                     #
    # ------------------------------------------------------------------ #

    async def _dispatch_event(self, event: dict):
        """Dispatch incoming events to handlers or pending action responses."""
        # Action response (has 'echo', no 'post_type').
        echo = event.get("echo")
        if echo and echo in self._pending_responses:
            future = self._pending_responses.pop(echo)
            if not future.done():
                future.set_result(event)
            return

        # Heartbeat — log at debug and move on.
        if event.get("meta_event_type") == "heartbeat":
            logger.debug("Heartbeat received")
            return

        # Message events.
        if event.get("post_type") == "message":
            message_type = event.get("message_type")
            handlers = self._handlers.get(f"{message_type}_message", [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Handler error: {e}", exc_info=True)

    # ------------------------------------------------------------------ #
    # Action API                                                         #
    # ------------------------------------------------------------------ #

    async def call_action(
        self,
        action: str,
        params: dict | None = None,
        timeout: float = 10.0,
    ) -> dict:
        """
        Invoke a OneBot action and await its response.

        OneBot v11 correlates responses to requests via the `echo` field,
        so we attach a unique echo, store a Future, and resolve it when
        _dispatch_event sees the matching echo come back.

        Returns:
            The full response dict (has `status`, `retcode`, `data`).
        """
        if not self.ws:
            raise RuntimeError("Not connected")

        echo = uuid.uuid4().hex
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[echo] = future

        payload = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }
        await self.ws.send(json.dumps(payload))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_responses.pop(echo, None)
            raise

    async def send_private_message(self, user_id: int, message: str):
        """Send a private message to a user (fire-and-forget)."""
        if not self.ws:
            raise RuntimeError("Not connected")
        payload = {
            "action": "send_private_msg",
            "params": {"user_id": user_id, "message": message},
            "echo": f"private_{user_id}",
        }
        await self.ws.send(json.dumps(payload))
        logger.debug(f"Sent private message to {user_id}")

    async def send_group_message(self, group_id: int, message: str):
        """Send a message to a group (fire-and-forget)."""
        if not self.ws:
            raise RuntimeError("Not connected")
        payload = {
            "action": "send_group_msg",
            "params": {"group_id": group_id, "message": message},
            "echo": f"group_{group_id}",
        }
        await self.ws.send(json.dumps(payload))
        logger.debug(f"Sent group message to {group_id}")

    # ------------------------------------------------------------------ #
    # Group name lookup                                                  #
    # ------------------------------------------------------------------ #

    async def refresh_group_list(self):
        """
        Bulk-populate the group_name cache via the `get_group_list` action.

        Call this once after each successful (re)connect.
        Silently no-ops if the action fails — get_group_name falls back to
        an on-demand get_group_info, and ultimately to the stringified ID.
        """
        try:
            response = await self.call_action("get_group_list", timeout=10.0)
        except Exception as e:
            logger.warning(f"get_group_list failed: {e}")
            return

        data = response.get("data") or []
        if not isinstance(data, list):
            return

        count = 0
        for entry in data:
            if not isinstance(entry, dict):
                continue
            gid = entry.get("group_id")
            name = entry.get("group_name")
            if isinstance(gid, int) and isinstance(name, str) and name:
                self._group_name_cache[gid] = name
                count += 1
        logger.info(f"Cached {count} group names from get_group_list")

    async def get_group_name(self, group_id: int) -> str:
        """
        Return a human-readable group name.

        Checks the cache first; on miss, tries `get_group_info`; on failure,
        falls back to `str(group_id)` so downstream code never breaks.
        """
        if group_id in self._group_name_cache:
            return self._group_name_cache[group_id]

        try:
            response = await self.call_action(
                "get_group_info",
                {"group_id": group_id},
                timeout=5.0,
            )
            data = response.get("data") or {}
            name = data.get("group_name")
            if isinstance(name, str) and name:
                self._group_name_cache[group_id] = name
                return name
        except Exception as e:
            logger.debug(f"get_group_info({group_id}) failed: {e}")

        return str(group_id)

    # ------------------------------------------------------------------ #
    # Shutdown                                                           #
    # ------------------------------------------------------------------ #

    async def close(self):
        """Close the WebSocket connection and stop the reconnect loop."""
        self._stop_event.set()
        self._running = False
        if self.ws:
            await self.ws.close()
            logger.info("Connection closed")
