from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .model import ModelClient, load_model_config


def load_qianwen_set(path: Path) -> Dict[str, Any]:
    """Compatibility helper for the old JSON-based config path."""

    config = load_model_config(legacy_config_path=path)
    return {
        "provider": config.provider,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "timeout_seconds": config.timeout_seconds,
        "repeat_penalty": config.repeat_penalty,
        "presence_penalty": config.presence_penalty,
        "frequency_penalty": config.frequency_penalty,
        "seed": config.seed,
    }


def call_qianwen(prompt: str, qianwen_set: Dict[str, Any]) -> str:
    """Compatibility wrapper.

    New code should call `ModelClient.generate(...)` directly.
    """

    client = ModelClient(load_model_config_from_dict(qianwen_set))
    return client.generate(messages=_messages(prompt))


def unload_qianwen_model(qianwen_set: Dict[str, Any]) -> None:
    """Compatibility wrapper for unloading local Ollama models."""

    client = ModelClient(load_model_config_from_dict(qianwen_set))
    client.unload()


def load_model_config_from_dict(data: Dict[str, Any]):
    from .model.config import ModelConfig

    provider = data.get("provider", "local")
    if provider not in {"local", "api"}:
        base_url = data.get("base_url", "")
        provider = "local" if "127.0.0.1" in base_url or "localhost" in base_url else "api"

    return ModelConfig(
        provider=provider,
        base_url=data["base_url"],
        api_key=data.get("api_key"),
        model=data["model"],
        temperature=float(data.get("temperature", 0.82)),
        top_p=float(data.get("top_p", 0.92)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout_seconds=int(data.get("timeout_seconds", 1200)),
        repeat_penalty=data.get("repeat_penalty"),
        presence_penalty=data.get("presence_penalty"),
        frequency_penalty=data.get("frequency_penalty"),
        seed=data.get("seed"),
    )


def _messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "你是番茄短故事执行作者。"
                "必须保持第一人称、强连续性、高冲突、高反转、高情绪密度，只输出正文。"
            ),
        },
        {"role": "user", "content": "/no_think\n" + prompt},
    ]
