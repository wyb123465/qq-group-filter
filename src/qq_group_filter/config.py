"""Configuration management using pydantic-settings."""

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Bot configuration loaded from .env file."""

    # OneBot WebSocket configuration
    onebot_ws_url: str = Field(
        default="ws://localhost:3001",
        description="OneBot v11 WebSocket server URL"
    )
    onebot_access_token: str = Field(
        default="",
        description="OneBot access token for authentication (optional)"
    )
    bot_qq: int = Field(
        description="Bot's QQ number"
    )

    # LLM Provider configuration
    llm_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="OpenAI-compatible API base URL"
    )
    llm_api_key: str = Field(
        description="LLM API key"
    )
    llm_model: str = Field(
        default="deepseek-chat",
        description="Model name to use"
    )
    llm_timeout: int = Field(
        default=30,
        description="API request timeout in seconds"
    )

    # Storage configuration
    db_path: str = Field(
        default="./data/messages.db",
        description="SQLite database file path"
    )

    # Monitoring configuration
    monitored_groups: list[int] | None = Field(
        default=None,
        description="List of group IDs to monitor (None = monitor all)"
    )

    # Scheduled digest push
    digest_hour: int = Field(
        default=8,
        description="Hour of day (0-23) to push daily digest. Set to -1 to disable."
    )

    @field_validator("monitored_groups", mode="before")
    @classmethod
    def parse_monitored_groups(cls, value):
        """Parse comma-separated group IDs from .env files."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return [
                int(group_id.strip())
                for group_id in value.split(",")
                if group_id.strip()
            ]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
