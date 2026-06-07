"""Tests for message storage and retrieval."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from qq_group_filter.persistence import MessageStore
from qq_group_filter.models import GroupMessage


@pytest.fixture
async def store():
    """Create an in-memory store for testing."""
    store = MessageStore(":memory:")
    await store.init_db()
    yield store
    await store.close()


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_init_db(store):
    """Test that database initializes correctly."""
    # Store fixture already calls init_db, just verify it doesn't crash
    assert store is not None


@pytest.mark.asyncio
async def test_init_db_creates_fts_table(tmp_path):
    """Test that database initializes the documented FTS5 table."""
    db_path = tmp_path / "messages.db"
    store = MessageStore(str(db_path))
    await store.init_db()
    await store.close()

    conn = sqlite3.connect(db_path)
    row = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'messages_fts'
    """).fetchone()
    conn.close()

    assert row is not None


@pytest.mark.asyncio
async def test_save_and_search_message(store):
    """Test saving and searching a message."""
    msg = GroupMessage(
        message_id=12345,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="张三",
        message="大家好，有人知道哪里可以租GPU吗",
        timestamp=datetime.now()
    )

    await store.save_group_message(msg)

    # Search with keyword
    results = await store.search_messages("GPU")
    assert len(results) == 1
    assert results[0].message_id == 12345
    assert results[0].user_nickname == "张三"
    assert "GPU" in results[0].message


@pytest.mark.asyncio
async def test_save_idempotent(store):
    """Test that saving the same message twice doesn't duplicate."""
    msg = GroupMessage(
        message_id=12345,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="张三",
        message="重复消息测试",
        timestamp=datetime.now()
    )

    await store.save_group_message(msg)
    await store.save_group_message(msg)  # Save again

    results = await store.search_messages("重复")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_with_time_filter(store):
    """Test searching with time range filter."""
    now = datetime.now()

    # Old message
    old_msg = GroupMessage(
        message_id=1,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="张三",
        message="昨天的GPU讨论",
        timestamp=now - timedelta(days=2)
    )

    # Recent message
    recent_msg = GroupMessage(
        message_id=2,
        group_id=111,
        group_name="测试群",
        user_id=333,
        user_nickname="李四",
        message="今天的GPU优惠",
        timestamp=now
    )

    await store.save_group_message(old_msg)
    await store.save_group_message(recent_msg)

    # Search for messages in past 24 hours
    results = await store.search_messages(
        "GPU",
        start_time=now - timedelta(hours=24)
    )

    assert len(results) == 1
    assert results[0].message_id == 2


@pytest.mark.asyncio
async def test_search_with_group_filter(store):
    """Test searching within specific groups."""
    now = datetime.now()

    # Message in group 111
    msg1 = GroupMessage(
        message_id=1,
        group_id=111,
        group_name="技术群",
        user_id=222,
        user_nickname="张三",
        message="Python实习机会",
        timestamp=now
    )

    # Message in group 222
    msg2 = GroupMessage(
        message_id=2,
        group_id=222,
        group_name="求职群",
        user_id=333,
        user_nickname="李四",
        message="Java实习机会",
        timestamp=now
    )

    await store.save_group_message(msg1)
    await store.save_group_message(msg2)

    # Search only in group 111
    results = await store.search_messages("实习", group_ids=[111])
    assert len(results) == 1
    assert results[0].group_id == 111


@pytest.mark.asyncio
async def test_chinese_fts(store):
    """Test FTS5 with Chinese text."""
    msg = GroupMessage(
        message_id=1,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="测试",
        message="我在找深度学习相关的实习岗位，有推荐吗？",
        timestamp=datetime.now()
    )

    await store.save_group_message(msg)

    # Search with different keywords
    for keyword in ["深度学习", "实习", "岗位"]:
        results = await store.search_messages(keyword)
        assert len(results) == 1


@pytest.mark.asyncio
async def test_search_matches_non_adjacent_fts_terms(store):
    """Test search can match terms that are not an exact LIKE phrase."""
    msg = GroupMessage(
        message_id=2,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="测试",
        message="GPU server rental is cheap today",
        timestamp=datetime.now()
    )

    await store.save_group_message(msg)

    results = await store.search_messages("GPU cheap")

    assert len(results) == 1
    assert results[0].message_id == 2


@pytest.mark.asyncio
async def test_like_fallback_matches_separate_terms_in_contiguous_chinese(store):
    """Fallback search should match all terms even when the original text is contiguous."""
    msg = GroupMessage(
        message_id=3,
        group_id=111,
        group_name="测试群",
        user_id=222,
        user_nickname="测试",
        message="我们公司有实习机会，欢迎投递",
        timestamp=datetime.now()
    )

    await store.save_group_message(msg)

    results = await store.search_messages("实习 机会")

    assert len(results) == 1
    assert results[0].message_id == 3


@pytest.mark.asyncio
async def test_add_and_get_interests(store):
    """Test adding and retrieving interests."""
    user_id = 123456

    await store.add_interest(user_id, "GPU租赁", "关注GPU服务器租赁信息")
    await store.add_interest(user_id, "实习机会", "关注算法岗实习")

    interests = await store.get_interests(user_id)
    assert len(interests) == 2
    assert interests[0].keyword in ["GPU租赁", "实习机会"]


@pytest.mark.asyncio
async def test_remove_interest(store):
    """Test removing an interest."""
    user_id = 123456

    await store.add_interest(user_id, "测试主题", "测试描述")
    interests = await store.get_interests(user_id)
    assert len(interests) == 1

    interest_id = interests[0].id
    await store.remove_interest(interest_id)

    interests = await store.get_interests(user_id)
    assert len(interests) == 0


@pytest.mark.asyncio
async def test_no_results(store):
    """Test searching when no results match."""
    results = await store.search_messages("不存在的关键词xyzabc")
    assert len(results) == 0
