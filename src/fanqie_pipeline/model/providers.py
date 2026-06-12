from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .config import ModelConfig


class ModelProvider:
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        raise NotImplementedError

    def unload(self) -> None:
        return None


class OpenAICompatibleProvider(ModelProvider):
    """Provider for both local and remote OpenAI-compatible chat APIs."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens if max_tokens is None else max_tokens,
        }
        for key in ["repeat_penalty", "presence_penalty", "frequency_penalty", "seed"]:
            value = getattr(self.config, key)
            if value is not None:
                payload[key] = value

        request = urllib.request.Request(
            self.config.chat_completions_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(self._connection_error_message()) from exc
        except TimeoutError as exc:
            raise RuntimeError(f"模型请求超时：{self.config.timeout_seconds} 秒。可调大 MODEL_TIMEOUT_SECONDS。") from exc

        return _extract_content(data)

    def unload(self) -> None:
        if self.config.provider != "local" or "11434" not in self.config.base_url:
            return
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(
                {
                    "model": self.config.model,
                    "prompt": "",
                    "keep_alive": 0,
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _connection_error_message(self) -> str:
        if self.config.provider == "local":
            return (
                "无法连接本地模型服务。请检查 LOCAL_MODEL_BASE_URL、LOCAL_MODEL_NAME，"
                "以及 Ollama/本地 OpenAI-compatible 服务是否已启动。"
            )
        return "无法连接远程模型 API。请检查 API_MODEL_BASE_URL、API_MODEL_NAME、API_KEY 和网络。"


def _extract_content(data: Dict[str, Any]) -> str:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"模型返回格式不符合 OpenAI-compatible chat completions：{data}") from exc

    content = message.get("content", "").strip()
    if content:
        return content

    reasoning = message.get("reasoning", "").strip()
    if reasoning:
        raise RuntimeError("模型只返回了 reasoning，没有返回正文。请确认 Prompt 包含 /no_think，或换用非思考模式模型。")
    raise RuntimeError("模型返回为空，请检查模型服务、max_tokens 和模型模式。")
