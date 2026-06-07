"""LLM provider for OpenAI-compatible APIs."""

import httpx


class LLMProvider:
    """Client for OpenAI-compatible chat completion APIs."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 30):
        """
        Initialize LLM provider.

        Args:
            base_url: API base URL (e.g., https://api.deepseek.com/v1)
            api_key: API key for authentication
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Call chat completion API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response

        Raises:
            httpx.TimeoutException: Request timeout
            httpx.HTTPStatusError: HTTP error response
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Extract response text from OpenAI-compatible format
            return data["choices"][0]["message"]["content"]
