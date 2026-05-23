from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def load_qianwen_set(path: Path) -> Dict[str, Any]:
    """读取本地千问配置。你主要微调这个 JSON，不需要改代码。"""

    return json.loads(path.read_text(encoding="utf-8"))


def call_qianwen(prompt: str, qianwen_set: Dict[str, Any]) -> str:
    """调用本地千问。

    默认支持 OpenAI 兼容接口，例如 vLLM、LM Studio、Ollama 的兼容模式。
    如果你用的是命令行版千问，可以在这里新增 provider 分支。
    """

    provider = qianwen_set.get("provider", "openai_compatible")
    if provider != "openai_compatible":
        raise ValueError(f"暂不支持的 provider：{provider}")

    payload = {
        "model": qianwen_set["model"],
        "messages": _messages(prompt),
        "temperature": qianwen_set.get("temperature", 0.82),
        "top_p": qianwen_set.get("top_p", 0.92),
        "max_tokens": qianwen_set.get("max_tokens", 4096),
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        qianwen_set["base_url"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {qianwen_set.get('api_key', 'EMPTY')}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=qianwen_set.get("timeout_seconds", 180)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "无法连接本地千问接口。请检查 config/qianwen_sets/local_openai_compatible.json "
            "里的 base_url、model，以及千问服务是否已启动。"
        ) from exc

    message = data["choices"][0]["message"]
    content = message.get("content", "").strip()
    if content:
        return content

    # Qwen3 在部分本地服务里会把输出放进 reasoning。
    # 这通常说明没有关闭思考模式，给出清晰提示方便调参。
    reasoning = message.get("reasoning", "").strip()
    if reasoning:
        raise RuntimeError("模型只返回了 reasoning，没有返回正文。请确认 Prompt 包含 /no_think，或换用非思考模式模型。")
    raise RuntimeError("模型返回为空，请检查模型服务和 max_tokens 设置。")


def _messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "你是番茄短篇、红果短剧风执行作者。"
                "必须短句、高冲突、高反转、高情绪密度，只输出正文。"
            ),
        },
        {"role": "user", "content": "/no_think\n" + prompt},
    ]
