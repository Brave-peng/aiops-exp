from __future__ import annotations

from typing import Any


def setup_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """创建测试环境。

    第一版先返回结构化占位结果，真实 kubectl 操作后续在本模块内补齐。
    """
    return {
        "type": environment["type"],
        "namespace": environment["namespace"],
        "status": "pending",
        "message": "K8s 环境创建逻辑尚未接入。",
    }


def cleanup_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """清理测试环境。"""
    return {
        "type": environment["type"],
        "namespace": environment["namespace"],
        "status": "pending",
        "message": "K8s 环境清理逻辑尚未接入。",
    }
