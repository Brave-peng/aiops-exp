from __future__ import annotations

from typing import Any


def evaluate_mock(scenario: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """返回用于跑通流程的固定评估结果。"""
    return {
        "type": scenario["evaluation"]["type"],
        "status": "passed",
        "score": 1.0,
        "message": "mock 评估固定通过。",
        "proposal_present": bool(proposal),
    }
