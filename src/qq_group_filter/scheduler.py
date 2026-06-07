"""Scheduled digest push — fires once daily at the configured hour."""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DigestScheduler:
    """Push daily digest to all users with active interests."""

    def __init__(self, query_handler, store, client, digest_hour: int):
        """
        Args:
            query_handler: QueryHandler instance (generates digest text)
            store: MessageStore (queries user list)
            client: OneBotClient (sends QQ messages)
            digest_hour: 0-23, the local hour to fire. -1 disables the scheduler.
        """
        self._query_handler = query_handler
        self._store = store
        self._client = client
        self._digest_hour = digest_hour
        self._task: asyncio.Task | None = None

    def start(self):
        """Launch the background scheduler task."""
        if self._digest_hour < 0:
            logger.info("Digest scheduler disabled (DIGEST_HOUR = -1)")
            return
        if self._task and not self._task.done():
            logger.debug("Digest scheduler already running")
            return
        self._task = asyncio.create_task(self._run())
        logger.info(f"Digest scheduler started — daily push at {self._digest_hour:02d}:00")

    async def stop(self):
        """Cancel the background task."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        """Loop: sleep until next target hour, push, repeat."""
        try:
            while True:
                delay = self._seconds_until_next_fire()
                logger.debug(f"Digest scheduler sleeping {delay}s until next fire")
                await asyncio.sleep(delay)
                await self._push_all()
        except asyncio.CancelledError:
            return

    def _seconds_until_next_fire(self) -> float:
        """Calculate seconds from now until the next occurrence of digest_hour:00."""
        now = datetime.now()
        target = now.replace(hour=self._digest_hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    async def _push_all(self):
        """Push digest to every user who has at least one active interest."""
        try:
            user_ids = await self._store.get_users_with_interests()
        except Exception as e:
            logger.error(f"Failed to get user list for digest: {e}")
            return

        logger.info(f"Pushing daily digest to {len(user_ids)} user(s)")

        for user_id in user_ids:
            try:
                digest = await self._query_handler.generate_daily_digest(user_id)
                if "没有" not in digest:
                    await self._client.send_private_message(user_id, digest)
            except Exception as e:
                logger.error(f"Failed to push digest to {user_id}: {e}")
