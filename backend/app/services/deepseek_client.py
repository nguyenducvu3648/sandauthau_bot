"""LLM API client - support nhiều provider."""
import json
import httpx
from typing import Optional, Dict, Any
from app.config import settings


class DeepSeekClient:
    """Singleton client cho LLM API (DeepSeek/Claude/OpenAI)."""

    _instance: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._instance is None:
            # Chọn provider
            provider = settings.LLM_PROVIDER.lower()

            if provider == "claude":
                headers = {
                    "x-api-key": settings.CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            elif provider == "openai":
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
            else:  # deepseek
                headers = {
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                }

            cls._instance = httpx.AsyncClient(timeout=30.0, headers=headers)
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.aclose()
            cls._instance = None

    @classmethod
    async def chat(
        cls,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None
    ) -> str:
        """Gọi LLM API."""
        client = cls.get_client()
        provider = settings.LLM_PROVIDER.lower()

        # Chuyển messages sang prompt
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        prompt = "\n\n".join(prompt_parts)

        if response_format == "json":
            prompt += "\n\nTrả về ONLY valid JSON, không markdown fence."

        endpoint = getattr(settings, f"{provider.upper()}_ENDPOINT")

        # OpenAI-compatible endpoint (base_url kết thúc bằng /v1) dùng format "messages"
        if endpoint.rstrip("/").endswith("/v1"):
            payload = {
                "model": getattr(settings, f"{provider.upper()}_MODEL"),
                "messages": messages,
                "stream": False,
                "temperature": temperature or getattr(settings, f"{provider.upper()}_TEMPERATURE"),
                "max_tokens": max_tokens or getattr(settings, f"{provider.upper()}_MAX_TOKENS"),
            }
            response = await client.post(endpoint.rstrip("/") + "/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if choices:
                return choices[0].get("message", {}).get("content", "") or ""
            return data.get("response", data.get("text", ""))

        payload = {
            "model": getattr(settings, f"{provider.upper()}_MODEL"),
            "prompt": prompt,
            "stream": False,
            "temperature": temperature or getattr(settings, f"{provider.upper()}_TEMPERATURE"),
            "max_tokens": max_tokens or getattr(settings, f"{provider.upper()}_MAX_TOKENS"),
        }

        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        data = response.json()

        # xah.io format: response.text
        return data.get("response", data.get("text", data.get("content", "")))

    @classmethod
    async def chat_stream(
        cls,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Streaming version của chat.

        Yields:
            Từng chunk text từ response stream
        """
        client = cls.get_client()
        provider = settings.LLM_PROVIDER.lower()

        payload = {
            "model": getattr(settings, f"{provider.upper()}_MODEL"),
            "messages": messages,
            "temperature": temperature or getattr(settings, f"{provider.upper()}_TEMPERATURE"),
            "max_tokens": max_tokens or 2000,
            "stream": True
        }

        endpoint = getattr(settings, f"{provider.upper()}_ENDPOINT")
        url = endpoint.rstrip("/") + "/chat/completions" if endpoint.rstrip("/").endswith("/v1") else endpoint

        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Chunk usage / keepalive / rõng: không có choices
                    choices = data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
                elif line.startswith("event:") or line.strip() == "":
                    continue
