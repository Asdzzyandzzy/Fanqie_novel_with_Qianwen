from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_MODEL = "hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M"
DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_MODEL = "gpt-4o-mini"


@dataclass
class ModelConfig:
    """Normalized model runtime config.

    The rest of the app should not care whether this came from `.env`,
    a legacy JSON config, Ollama, or a remote API key.
    """

    provider: str
    base_url: str
    model: str
    api_key: Optional[str] = None
    temperature: float = 0.82
    top_p: float = 0.92
    max_tokens: int = 4096
    timeout_seconds: int = 1200
    repeat_penalty: Optional[float] = 1.08
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    seed: Optional[int] = None

    @property
    def chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    @property
    def display_name(self) -> str:
        return f"{self.provider} / {self.model}"


def load_model_config(env_path: Optional[Path] = None, legacy_config_path: Optional[Path] = None) -> ModelConfig:
    """Load model config from `.env`, environment variables, or legacy JSON.

    `legacy_config_path` is kept for compatibility with the existing
    `config/qianwen_sets/*.json` workflow. New code should prefer `.env`.
    """

    env_values = _load_env_file(env_path or Path(".env"))
    merged_env = {**env_values, **os.environ}

    if legacy_config_path is not None:
        return _from_legacy_json(legacy_config_path, merged_env)

    provider = merged_env.get("MODEL_PROVIDER", "local").strip().lower()
    if provider == "local":
        return _from_local_env(merged_env)
    if provider == "api":
        return _from_api_env(merged_env)
    raise ValueError("MODEL_PROVIDER 配置错误。只支持 local 或 api。")


def _from_local_env(env: Dict[str, str]) -> ModelConfig:
    return ModelConfig(
        provider="local",
        base_url=env.get("LOCAL_MODEL_BASE_URL", DEFAULT_LOCAL_BASE_URL),
        model=env.get("LOCAL_MODEL_NAME", DEFAULT_LOCAL_MODEL),
        api_key=env.get("LOCAL_API_KEY", "ollama"),
        temperature=_float_env(env, "MODEL_TEMPERATURE", 0.82),
        top_p=_float_env(env, "MODEL_TOP_P", 0.92),
        max_tokens=_int_env(env, "MODEL_MAX_TOKENS", 4096),
        timeout_seconds=_int_env(env, "MODEL_TIMEOUT_SECONDS", 1200),
        repeat_penalty=_optional_float_env(env, "MODEL_REPEAT_PENALTY", 1.08),
        presence_penalty=_optional_float_env(env, "MODEL_PRESENCE_PENALTY", None),
        frequency_penalty=_optional_float_env(env, "MODEL_FREQUENCY_PENALTY", None),
        seed=_optional_int_env(env, "MODEL_SEED", None),
    )


def _from_api_env(env: Dict[str, str]) -> ModelConfig:
    api_key = env.get("API_KEY")
    if not api_key:
        raise ValueError("MODEL_PROVIDER=api 时必须配置 API_KEY。请在 .env 中设置 API_KEY。")
    return ModelConfig(
        provider="api",
        base_url=env.get("API_MODEL_BASE_URL", DEFAULT_API_BASE_URL),
        model=env.get("API_MODEL_NAME", DEFAULT_API_MODEL),
        api_key=api_key,
        temperature=_float_env(env, "MODEL_TEMPERATURE", 0.82),
        top_p=_float_env(env, "MODEL_TOP_P", 0.92),
        max_tokens=_int_env(env, "MODEL_MAX_TOKENS", 4096),
        timeout_seconds=_int_env(env, "MODEL_TIMEOUT_SECONDS", 1200),
        repeat_penalty=_optional_float_env(env, "MODEL_REPEAT_PENALTY", None),
        presence_penalty=_optional_float_env(env, "MODEL_PRESENCE_PENALTY", None),
        frequency_penalty=_optional_float_env(env, "MODEL_FREQUENCY_PENALTY", None),
        seed=_optional_int_env(env, "MODEL_SEED", None),
    )


def _from_legacy_json(path: Path, env: Dict[str, str]) -> ModelConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    provider = _normalize_legacy_provider(data.get("provider", "openai_compatible"), data.get("base_url", ""))
    base_url = data.get("base_url", DEFAULT_LOCAL_BASE_URL)
    if base_url.rstrip("/").endswith("/chat/completions"):
        base_url = base_url.rsplit("/chat/completions", 1)[0]
    model = data.get("model")
    if not model:
        raise ValueError(f"模型配置文件缺少 model：{path}")
    api_key = data.get("api_key")
    if provider == "api" and not api_key:
        api_key = env.get("API_KEY")
    if provider == "api" and not api_key:
        raise ValueError("API 模型配置缺少 API_KEY。请设置环境变量 API_KEY 或在配置文件中提供 api_key。")
    return ModelConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key or ("ollama" if provider == "local" else None),
        temperature=float(data.get("temperature", env.get("MODEL_TEMPERATURE", 0.82))),
        top_p=float(data.get("top_p", env.get("MODEL_TOP_P", 0.92))),
        max_tokens=int(data.get("max_tokens", env.get("MODEL_MAX_TOKENS", 4096))),
        timeout_seconds=int(data.get("timeout_seconds", env.get("MODEL_TIMEOUT_SECONDS", 1200))),
        repeat_penalty=data.get("repeat_penalty"),
        presence_penalty=data.get("presence_penalty"),
        frequency_penalty=data.get("frequency_penalty"),
        seed=data.get("seed"),
    )


def _normalize_legacy_provider(provider: str, base_url: str) -> str:
    if provider in {"local", "api"}:
        return provider
    if "127.0.0.1" in base_url or "localhost" in base_url:
        return "local"
    return "api"


def _load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _float_env(env: Dict[str, str], key: str, default: float) -> float:
    return float(env.get(key, default))


def _int_env(env: Dict[str, str], key: str, default: int) -> int:
    return int(env.get(key, default))


def _optional_float_env(env: Dict[str, str], key: str, default: Optional[float]) -> Optional[float]:
    value = env.get(key)
    if value in (None, ""):
        return default
    return float(value)


def _optional_int_env(env: Dict[str, str], key: str, default: Optional[int]) -> Optional[int]:
    value = env.get(key)
    if value in (None, ""):
        return default
    return int(value)
