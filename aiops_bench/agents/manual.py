from __future__ import annotations

import json
from typing import Any

from aiops_bench.actions import render_action_contract


def build_agent_prompt(scenario: dict[str, Any]) -> str:
    """根据场景生成给 Agent 的作答提示词。"""
    environment = scenario["environment"]
    allowed_actions = scenario["solution_contract"]["allowed_actions"]

    lines = [
        f"# {scenario['name']}",
        "",
        "## 场景描述",
        str(scenario.get("description", "")).strip() or "无",
        "",
        "## 测试环境",
        f"- 类型：{environment['type']}",
        f"- namespace：{environment['namespace']}",
        "",
        "## 已注入故障",
    ]

    for fault in scenario["faults"]:
        lines.extend(
            [
                f"- id：{fault['id']}",
                f"  - 类型：{fault['type']}",
                f"  - 目标：{json.dumps(fault['target'], ensure_ascii=False)}",
                f"  - 参数：{json.dumps(fault['spec'], ensure_ascii=False)}",
            ]
        )

    lines.extend(
        [
            "",
            "## 作答要求",
            scenario["agent_task"]["instruction"].strip(),
            "",
            "## 允许提出的修复动作类型",
        ]
    )
    lines.extend(f"- {action}" for action in allowed_actions)
    lines.extend(
        [
            "",
            "## 动作参数契约",
            render_action_contract(allowed_actions),
            "",
            "## 建议输出格式",
            "请返回 JSON，结构如下：",
            "",
            "```json",
            "{",
            '  "diagnosis": "诊断结论",',
            '  "evidence": ["依据 1", "依据 2"],',
            '  "proposed_actions": [',
            "    {",
            '      "type": "kubectl_scale",',
            '      "params": {},',
            '      "reason": "建议原因"',
            "    }",
            "  ]",
            "}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def pending_manual_proposal() -> dict[str, Any]:
    """返回 manual 模式的占位结果。"""
    return {
        "status": "pending",
        "message": "manual 模式已在 report.md 和 run.json 中生成提示词，请人工获取 Agent 建议。",
    }
