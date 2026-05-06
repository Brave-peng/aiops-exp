from __future__ import annotations

from typing import Any


def inject_faults(faults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """注入 Chaos Mesh 故障。

    第一版先返回结构化占位结果，真实 CRD 创建后续在本模块内补齐。
    """
    return [
        {
            "id": fault["id"],
            "type": fault["type"],
            "status": "pending",
            "message": "Chaos Mesh 故障注入逻辑尚未接入。",
        }
        for fault in faults
    ]


def cleanup_faults(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清理已注入故障。"""
    return [
        {
            "id": handle["id"],
            "type": handle["type"],
            "status": "pending",
            "message": "Chaos Mesh 故障清理逻辑尚未接入。",
        }
        for handle in handles
    ]
