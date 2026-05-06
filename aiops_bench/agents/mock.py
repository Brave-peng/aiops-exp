from __future__ import annotations

from typing import Any


def solve_with_mock_agent(scenario: dict[str, Any]) -> dict[str, Any]:
    """返回用于跑通流程的固定 Agent 建议。"""
    namespace = scenario["environment"]["namespace"]
    return {
        "diagnosis": "模拟诊断：目标服务出现 CPU 压力。",
        "evidence": ["这是 mock 模式返回的占位依据。"],
        "proposed_actions": [
            {
                "type": "kubectl_scale",
                "params": {
                    "namespace": namespace,
                    "deployment": "demo-service",
                    "replicas": 2,
                },
                "reason": "模拟智能体建议增加副本数，缓解 CPU 压力。",
            }
        ],
    }
