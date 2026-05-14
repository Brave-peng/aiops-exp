from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_TIMEOUT_SECONDS = 120


class DeepSeekError(RuntimeError):
    """DeepSeek API 调用或响应解析失败。"""


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: int | None = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """调用 DeepSeek Chat Completions API，并解析 JSON object 响应。"""
    api_key = _read_api_key()
    selected_model = model or read_model()
    selected_base_url = base_url or read_base_url()
    selected_timeout = timeout_seconds or read_timeout_seconds()
    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{selected_base_url.rstrip('/')}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=selected_timeout) as response:
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


def build_agent_metadata(role: str, model: str | None = None) -> dict[str, Any]:
    """构造写入结果文件的 AI Agent 元数据。"""
    return {
        "role": role,
        "provider": "deepseek",
        "model": model or read_model(),
        "base_url": read_base_url(),
    }


def read_model(specific_env_name: str | None = None) -> str:
    """读取模型名，允许 proposer/judge 分别覆盖。"""
    names = []
    if specific_env_name:
        names.append(specific_env_name)
    names.extend(["AIOPS_DEEPSEEK_MODEL", "DEEPSEEK_MODEL"])
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return DEFAULT_MODEL


def read_base_url() -> str:
    """读取 DeepSeek OpenAI-compatible base_url。"""
    return os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("AIOPS_DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL


def read_timeout_seconds() -> int:
    """读取 API 超时时间。"""
    value = os.environ.get("AIOPS_DEEPSEEK_TIMEOUT_SECONDS") or os.environ.get("DEEPSEEK_TIMEOUT_SECONDS")
    if not value:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return int(value)
    except ValueError as exc:
        raise DeepSeekError("DeepSeek timeout must be an integer") from exc


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
