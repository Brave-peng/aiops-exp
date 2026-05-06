from __future__ import annotations

from typing import Any


def evaluate_manual(scenario: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """返回人工评估占位结果。"""
    return {
        "type": scenario["evaluation"]["type"],
        "status": "pending",
        "message": "当前版本由人工 review Agent 建议。",
        "proposal_present": bool(proposal),
    }
