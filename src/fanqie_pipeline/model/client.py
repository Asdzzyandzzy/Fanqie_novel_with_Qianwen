from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .config import ModelConfig, load_model_config
from .providers import OpenAICompatibleProvider


class ModelClient:
    """Single model interface used by the novel generation pipeline."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.provider = OpenAICompatibleProvider(config)

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "ModelClient":
        return cls(load_model_config(env_path=env_path))

    @classmethod
    def from_config_file(cls, path: Path, env_path: Optional[Path] = None) -> "ModelClient":
        return cls(load_model_config(env_path=env_path, legacy_config_path=path))

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        return self.provider.generate(messages=messages, temperature=temperature, max_tokens=max_tokens)

    def unload(self) -> None:
        self.provider.unload()
