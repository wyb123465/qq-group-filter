"""Message storage and retrieval using SQLite."""

import aiosqlite
import re
from datetime import datetime
from pathlib import Path

from qq_group_filter.models import GroupMessage, Interest


class MessageStore:
    """Persistent storage for group messages and user interests."""

    def __init__(self, db_path: str):
        """Initialize store with database path."""
        self.db_path = db_path
        self._db = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        """Establish database connection."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def init_db(self):
        """Initialize database schema with tables."""
        if not self._db:
            await self.connect()

        # Create group_messages table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                message_id INTEGER PRIMARY KEY,
                group_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                user_nickname TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)

        # Create indexes for efficient search
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_timestamp
            ON group_messages(group_id, timestamp)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON group_messages(timestamp)
        """)

        await self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                message,
                tokenize='unicode61'
            )
        """)

        # Create interests table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                description TEXT,
                created_at INTEGER NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_active
            ON interests(user_id, active)
        """)

        await self._db.commit()

    async def save_group_message(self, msg: GroupMessage):
        """Save a group message (idempotent by message_id)."""
        await self._db.execute("""
            INSERT OR REPLACE INTO group_messages
            (message_id, group_id, group_name, user_id, user_nickname, message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            msg.message_id,
            msg.group_id,
            msg.group_name,
            msg.user_id,
            msg.user_nickname,
            msg.message,
            int(msg.timestamp.timestamp())
        ))
        await self._db.execute(
            "DELETE FROM messages_fts WHERE rowid = ?",
            (msg.message_id,)
        )
        await self._db.execute(
            "INSERT INTO messages_fts(rowid, message) VALUES (?, ?)",
            (msg.message_id, msg.message)
        )
        await self._db.commit()

    def _build_fts_query(self, query: str) -> str:
        """Build a conservative FTS5 query from user text."""
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", query)
        return " ".join(tokens)

    async def search_messages(
        self,
        query: str,
        group_ids: list[int] | None = None,
        start_time: datetime | None = None,
        limit: int = 50
    ) -> list[GroupMessage]:
        """
        Search messages — FTS5 first (AND of extracted tokens), LIKE fallback.

        Args:
            query: Search query (keywords; caller should strip stop-words)
            group_ids: Filter by specific groups (None = all groups)
            start_time: Filter messages after this time (None = no filter)
            limit: Maximum results to return

        Returns:
            List of matching GroupMessage objects
        """
        fts_query = self._build_fts_query(query)
        if fts_query:
            messages = await self._search_messages_fts(
                fts_query=fts_query,
                group_ids=group_ids,
                start_time=start_time,
                limit=limit
            )
            if messages:
                return messages

        return await self._search_messages_like(
            query=query,
            group_ids=group_ids,
            start_time=start_time,
            limit=limit
        )

    async def _search_messages_fts(
        self,
        fts_query: str,
        group_ids: list[int] | None,
        start_time: datetime | None,
        limit: int
    ) -> list[GroupMessage]:
        """Search messages using SQLite FTS5."""
        sql_parts = ["""
            SELECT gm.message_id, gm.group_id, gm.group_name, gm.user_id,
                   gm.user_nickname, gm.message, gm.timestamp
            FROM messages_fts
            JOIN group_messages gm ON gm.message_id = messages_fts.rowid
            WHERE messages_fts MATCH ?
        """]
        params = [fts_query]

        if group_ids is not None:
            placeholders = ','.join('?' * len(group_ids))
            sql_parts.append(f"AND gm.group_id IN ({placeholders})")
            params.extend(group_ids)

        if start_time is not None:
            sql_parts.append("AND gm.timestamp >= ?")
            params.append(int(start_time.timestamp()))

        sql_parts.append("ORDER BY gm.timestamp DESC LIMIT ?")
        params.append(limit)

        sql = ' '.join(sql_parts)
        try:
            cursor = await self._db.execute(sql, params)
            rows = await cursor.fetchall()
        except aiosqlite.OperationalError:
            return []

        return self._rows_to_messages(rows)

    async def _search_messages_like(
        self,
        query: str,
        group_ids: list[int] | None,
        start_time: datetime | None,
        limit: int
    ) -> list[GroupMessage]:
        """Search messages using LIKE as a compatibility fallback."""
        sql_parts = ["""
            SELECT message_id, group_id, group_name, user_id,
                   user_nickname, message, timestamp
            FROM group_messages
            WHERE 1 = 1
        """]
        params = []

        tokens = self._build_fts_query(query).split()
        if tokens:
            for token in tokens:
                sql_parts.append("AND message LIKE ?")
                params.append(f"%{token}%")
        else:
            sql_parts.append("AND message LIKE ?")
            params.append(f"%{query}%")

        if group_ids is not None:
            placeholders = ','.join('?' * len(group_ids))
            sql_parts.append(f"AND group_id IN ({placeholders})")
            params.extend(group_ids)

        if start_time is not None:
            sql_parts.append("AND timestamp >= ?")
            params.append(int(start_time.timestamp()))

        sql_parts.append("ORDER BY timestamp DESC LIMIT ?")
        params.append(limit)

        sql = ' '.join(sql_parts)
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()

        return self._rows_to_messages(rows)

    def _rows_to_messages(self, rows) -> list[GroupMessage]:
        """Convert SQLite rows into GroupMessage models."""
        return [
            GroupMessage(
                message_id=row['message_id'],
                group_id=row['group_id'],
                group_name=row['group_name'],
                user_id=row['user_id'],
                user_nickname=row['user_nickname'],
                message=row['message'],
                timestamp=datetime.fromtimestamp(row['timestamp'])
            )
            for row in rows
        ]

    async def add_interest(self, user_id: int, keyword: str, description: str):
        """Add a new interest for a user."""
        await self._db.execute("""
            INSERT INTO interests (user_id, keyword, description, created_at, active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_id, keyword, description, int(datetime.now().timestamp())))
        await self._db.commit()

    async def get_interests(self, user_id: int) -> list[Interest]:
        """Get all active interests for a user."""
        cursor = await self._db.execute("""
            SELECT id, user_id, keyword, description, created_at, active
            FROM interests
            WHERE user_id = ? AND active = 1
            ORDER BY created_at DESC
        """, (user_id,))
        rows = await cursor.fetchall()

        return [
            Interest(
                id=row['id'],
                user_id=row['user_id'],
                keyword=row['keyword'],
                description=row['description'],
                created_at=datetime.fromtimestamp(row['created_at']),
                active=bool(row['active'])
            )
            for row in rows
        ]

    async def remove_interest(self, interest_id: int):
        """Remove (deactivate) an interest."""
        await self._db.execute("""
            UPDATE interests SET active = 0 WHERE id = ?
        """, (interest_id,))
        await self._db.commit()

    async def get_users_with_interests(self) -> list[int]:
        """Return distinct user_ids that have at least one active interest."""
        cursor = await self._db.execute("""
            SELECT DISTINCT user_id FROM interests WHERE active = 1
        """)
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]

    async def get_latest_message_id(self, group_id: int) -> int | None:
        """
        Return the highest message_id stored for a group, or None if empty.

        Used by the backfill service to decide what's new: anything with
        message_id > this value hasn't been seen yet.

        Note: OneBot's message_id is a 64-bit signed integer that monotonically
        increases per-group, so MAX() is a valid "latest" cursor.
        """
        cursor = await self._db.execute(
            "SELECT MAX(message_id) AS latest FROM group_messages WHERE group_id = ?",
            (group_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        latest = row["latest"]
        return int(latest) if latest is not None else None
