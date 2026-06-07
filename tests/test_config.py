"""Tests for environment configuration parsing."""

from qq_group_filter.config import Config


def test_monitored_groups_accepts_comma_separated_env(monkeypatch):
    """MONITORED_GROUPS should match the documented comma-separated .env format."""
    monkeypatch.setenv("BOT_QQ", "123456")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("MONITORED_GROUPS", "111, 222,333")

    config = Config(_env_file=None)

    assert config.monitored_groups == [111, 222, 333]
