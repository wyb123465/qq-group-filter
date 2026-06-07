"""Tests for LLM provider."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from qq_group_filter.llm_provider import LLMProvider


@pytest.fixture
def provider():
    """Create a test LLM provider."""
    return LLMProvider(
        base_url="https://api.test.com/v1",
        api_key="test-key",
        model="test-model",
        timeout=30
    )


@pytest.mark.asyncio
async def test_successful_completion(provider):
    """Test successful chat completion."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "这是测试回复"
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_post.return_value.raise_for_status = lambda: None

        result = await provider.chat_completion([
            {"role": "user", "content": "测试问题"}
        ])

        assert result == "这是测试回复"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_timeout_error(provider):
    """Test timeout handling."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(httpx.TimeoutException):
            await provider.chat_completion([
                {"role": "user", "content": "测试问题"}
            ])


@pytest.mark.asyncio
async def test_http_error(provider):
    """Test HTTP error handling."""
    with patch("httpx.AsyncClient.post") as mock_post:
        # Create a proper mock response
        mock_response = AsyncMock()
        mock_response.status_code = 401

        # Make raise_for_status raise the exception
        def raise_error():
            raise httpx.HTTPStatusError(
                "Unauthorized",
                request=AsyncMock(),
                response=mock_response
            )

        mock_response.raise_for_status = raise_error
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await provider.chat_completion([
                {"role": "user", "content": "测试问题"}
            ])
