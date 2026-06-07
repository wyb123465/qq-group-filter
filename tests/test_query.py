"""Tests for the query handler — focused on keyword extraction."""

import pytest

from datetime import datetime

from qq_group_filter.models import GroupMessage
from qq_group_filter.query import QueryHandler


@pytest.fixture
def handler():
    """QueryHandler with no real dependencies — we only test pure methods."""
    return QueryHandler(store=None, llm=None)


def test_extract_keywords_strips_time_and_fillers(handler):
    """The classic case that exposed the bug: stop-word soup → 0 hits."""
    keywords = handler._extract_keywords("最近群里有讨论GPU租赁吗")
    tokens = set(keywords.split())
    assert "GPU" in tokens
    assert "租赁" in tokens
    # The filler/time words must not survive — that's the whole point.
    assert "最近" not in tokens
    assert "群里" not in tokens
    assert "讨论" not in tokens
    assert "吗" not in tokens


def test_extract_keywords_pure_chinese(handler):
    """Stop-word boundaries shouldn't eat the actual topic."""
    keywords = handler._extract_keywords("昨天有人聊到实习机会吗")
    tokens = set(keywords.split())
    assert "实习机会" in tokens or {"实习", "机会"} <= tokens
    assert "昨天" not in tokens
    assert "聊" not in tokens


def test_extract_keywords_english_only(handler):
    """English passes through unchanged — no CJK stopword stripping applies."""
    keywords = handler._extract_keywords("any news about Kubernetes")
    tokens = set(keywords.split())
    assert "Kubernetes" in tokens
    assert "news" in tokens


def test_extract_keywords_empty_for_only_stopwords(handler):
    """If the query is *entirely* stop words, return empty so caller can fall back."""
    keywords = handler._extract_keywords("最近群里有讨论吗")
    # All time/filler/particle — nothing left.
    assert keywords == ""


def test_extract_time_range_recent(handler):
    """Smoke test for the 24h window."""
    from datetime import datetime, timedelta
    start = handler._extract_time_range("最近群里讨论了什么")
    delta = datetime.now() - start
    assert timedelta(hours=23) < delta < timedelta(hours=25)


def test_extract_time_range_default(handler):
    """No time word → 7 day default."""
    from datetime import datetime, timedelta
    start = handler._extract_time_range("GPU 租赁有讨论吗")
    delta = datetime.now() - start
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)


def test_broad_summary_query_detected(handler):
    """A general group summary should not become a narrow keyword search."""
    assert handler._is_broad_summary_query("总结下现在群里的信息")
    assert handler._is_broad_summary_query("概括一下今天群里聊了什么")
    assert not handler._is_broad_summary_query("最近群里有讨论GPU租赁吗")


@pytest.mark.asyncio
async def test_broad_summary_searches_recent_messages_without_keywords():
    """Broad summary queries should search recent messages instead of generic words."""

    class FakeStore:
        def __init__(self):
            self.calls = []

        async def search_messages(self, query, start_time=None, limit=50):
            self.calls.append({
                "query": query,
                "start_time": start_time,
                "limit": limit,
            })
            return [
                GroupMessage(
                    message_id=1,
                    group_id=100,
                    group_name="测试群",
                    user_id=200,
                    user_nickname="张三",
                    message="今晚讨论了安保和值班安排",
                    timestamp=datetime.now(),
                )
            ]

    class FakeLLM:
        async def chat_completion(self, messages):
            return "群里主要讨论了安保和值班安排。"

    store = FakeStore()
    handler = QueryHandler(store=store, llm=FakeLLM())

    result = await handler.handle_query(2605464216, "总结下现在群里的信息")

    assert store.calls[0]["query"] == ""
    assert store.calls[0]["limit"] == 50
    assert "安保" in result.summary
    assert result.sources
