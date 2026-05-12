from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


class DeepSeekError(RuntimeError):
    """DeepSeek API 调用或响应解析失败。"""


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """调用 DeepSeek Chat Completions API，并解析 JSON object 响应。"""
    api_key = _read_api_key()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeepSeekError(f"DeepSeek API HTTP {exc.code}: {_trim(detail)}") from exc
    except urllib.error.URLError as exc:
        raise DeepSeekError(f"DeepSeek API request failed: {exc.reason}") from exc

    try:
        envelope = json.loads(body)
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise DeepSeekError("DeepSeek API returned an unexpected response shape") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        parsed = _parse_fenced_json(content, exc)

    if not isinstance(parsed, dict):
        raise DeepSeekError("DeepSeek JSON response must be an object")
    return parsed


def _read_api_key() -> str:
    for name in ("ak-deepseek", "ak_deepseek", "AK_DEEPSEEK", "DEEPSEEK_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    raise DeepSeekError("DeepSeek API key is missing from environment")


def _parse_fenced_json(content: str, original: json.JSONDecodeError) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        try:
            data = json.loads("\n".join(lines))
        except json.JSONDecodeError:
            raise DeepSeekError("DeepSeek response content is not valid JSON") from original
        if isinstance(data, dict):
            return data
    raise DeepSeekError("DeepSeek response content is not valid JSON") from original


def _trim(value: str, limit: int = 500) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "..."
