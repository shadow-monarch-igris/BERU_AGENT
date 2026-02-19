from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

from beru.utils.config import get_config
from beru.utils.logger import get_logger

logger = get_logger("beru.llm")


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def generate_stream(  # type: ignore
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        pass


class OllamaClient(BaseLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        config = get_config()
        self.model = model or config.model.name
        self.base_url = base_url or config.model.base_url
        self.temperature = temperature or config.model.temperature
        self.max_tokens = max_tokens or config.model.max_tokens
        self.timeout = config.model.timeout

    async def _create_session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        return aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        async with await self._create_session() as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                },
            }

            if system:
                payload["system"] = system

            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama API error: {response.status} - {error_text}"
                    )

                data = await response.json()

                return LLMResponse(
                    text=data.get("response", ""),
                    model=data.get("model", self.model),
                    tokens_used=data.get("eval_count", 0)
                    + data.get("prompt_eval_count", 0),
                    finish_reason="stop" if data.get("done") else "incomplete",
                    metadata=data,
                )

    async def generate_stream(  # type: ignore
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        async with await self._create_session() as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                },
            }

            if system:
                payload["system"] = system

            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama API error: {response.status} - {error_text}"
                    )

                async for line in response.content:
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        async with await self._create_session() as session:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                },
            }

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama API error: {response.status} - {error_text}"
                    )

                data = await response.json()
                message = data.get("message", {})

                return LLMResponse(
                    text=message.get("content", ""),
                    model=data.get("model", self.model),
                    tokens_used=data.get("eval_count", 0)
                    + data.get("prompt_eval_count", 0),
                    finish_reason="stop" if data.get("done") else "incomplete",
                    metadata=data,
                )

    async def list_models(self) -> List[Dict[str, Any]]:
        async with await self._create_session() as session:
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                data = await response.json()
                return data.get("models", [])

    async def pull_model(self, model_name: str) -> bool:
        async with await self._create_session() as session:
            async with session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
            ) as response:
                return response.status == 200


class MockLLMClient(BaseLLMClient):
    def __init__(self, response: str = "Mock response"):
        self.response = response

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        return LLMResponse(text=self.response, model="mock")

    async def generate_stream(  # type: ignore
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        yield self.response

    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        return LLMResponse(text=self.response, model="mock")


def create_llm_client(
    provider: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    config = get_config()
    provider = provider or config.model.provider

    if provider == "ollama":
        return OllamaClient(**kwargs)

    if provider == "mock":
        return MockLLMClient(**kwargs)

    raise ValueError(f"Unknown LLM provider: {provider}")


_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    global _client
    if _client is None:
        _client = create_llm_client()
    return _client


def reset_llm_client() -> BaseLLMClient:
    global _client
    _client = create_llm_client()
    return _client
