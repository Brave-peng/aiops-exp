from __future__ import annotations

import json
from typing import Any

from aiops_bench.llm.deepseek import chat_json
from aiops_bench.observability import render_observations_markdown


SYSTEM_PROMPT = """你是一个 AIOps benchmark judge。
你需要根据场景、现场证据、proposer 建议和动作约束进行评分。
必须返回合法 JSON object，不要返回 Markdown。"""


def build_evaluation_prompt(
    scenario: dict[str, Any],
    observations: dict[str, Any],
    proposal: dict[str, Any],
) -> str:
    """构造 judge 输入。"""
    return "\n".join(
        [
            "# AIOps 评测任务",
            "",
            "## 场景",
            "```json",
            json.dumps(scenario, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Kubernetes 现场快照",
            render_observations_markdown(observations),
            "",
            "## Kubernetes 现场摘要 JSON",
            "```json",
            json.dumps(observations.get("summary", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Proposer 输出",
            "```json",
            json.dumps(proposal, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 输出要求",
            "只返回 JSON object，字段为 type、status、score、summary、strengths、risks、contract_violations、recommendation。",
            "status 必须是 passed 或 failed；score 必须是 0 到 1 的数字；recommendation 必须是 accept、revise 或 reject。",
            "如果故障 status 不是 active，需要在评分中指出实验注入未真实生效，不能把 CRD 创建成功等同于故障生效。",
        ]
    )


def evaluate_deepseek(
    scenario: dict[str, Any],
    observations: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """调用 DeepSeek 对 proposal 评分。"""
    prompt = build_evaluation_prompt(scenario, observations, proposal)
    evaluation = chat_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    evaluation["type"] = "deepseek"
    validate_evaluation(evaluation)
    return evaluation


def validate_evaluation(evaluation: dict[str, Any]) -> None:
    """校验 judge 输出的最小结构。"""
    if evaluation.get("type") != "deepseek":
        raise ValueError("evaluation.type must be 'deepseek'")
    if evaluation.get("status") not in {"passed", "failed"}:
        raise ValueError("evaluation.status must be 'passed' or 'failed'")
    score = evaluation.get("score")
    if not isinstance(score, int | float) or not 0 <= score <= 1:
        raise ValueError("evaluation.score must be a number between 0 and 1")
    for key in ("summary", "recommendation"):
        if not isinstance(evaluation.get(key), str) or not evaluation[key].strip():
            raise ValueError(f"evaluation.{key} must be a non-empty string")
    for key in ("strengths", "risks", "contract_violations"):
        if not isinstance(evaluation.get(key), list):
            raise ValueError(f"evaluation.{key} must be a list")
