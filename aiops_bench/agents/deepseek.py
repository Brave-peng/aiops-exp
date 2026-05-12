from __future__ import annotations

from typing import Any

from aiops_bench.agents.manual import build_agent_prompt
from aiops_bench.llm.deepseek import chat_json
from aiops_bench.observability import render_observations_markdown


SYSTEM_PROMPT = """你是一个 Kubernetes/AIOps 故障诊断智能体。
你只能提出修复建议，不能声称已经执行修复。
必须返回合法 JSON object，不要返回 Markdown。"""


def build_deepseek_proposal_prompt(
    scenario: dict[str, Any],
    observations: dict[str, Any],
) -> str:
    """构造 DeepSeek proposer 输入。"""
    base_prompt = build_agent_prompt(scenario)
    return (
        base_prompt
        + "\n## Kubernetes 现场快照\n"
        + render_observations_markdown(observations)
        + "\n## 严格输出要求\n"
        + "如果故障 status 不是 active，请把这视为实验注入问题，而不是业务服务 CPU 饱和问题。\n"
        + "只返回 JSON object，字段为 status、diagnosis、evidence、proposed_actions。\n"
        + "status 必须为 ready。proposed_actions 里的 type 必须来自允许动作类型。\n"
    )


def solve_with_deepseek_agent(
    scenario: dict[str, Any],
    observations: dict[str, Any],
) -> dict[str, Any]:
    """调用 DeepSeek 生成修复建议。"""
    prompt = build_deepseek_proposal_prompt(scenario, observations)
    proposal = chat_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    proposal.setdefault("status", "ready")
    validate_proposal(scenario, proposal)
    return proposal


def validate_proposal(scenario: dict[str, Any], proposal: dict[str, Any]) -> None:
    """校验 proposer 输出的最小结构和 action 白名单。"""
    if proposal.get("status") != "ready":
        raise ValueError("proposal.status must be 'ready'")
    if not isinstance(proposal.get("diagnosis"), str) or not proposal["diagnosis"].strip():
        raise ValueError("proposal.diagnosis must be a non-empty string")
    if not isinstance(proposal.get("evidence"), list):
        raise ValueError("proposal.evidence must be a list")
    actions = proposal.get("proposed_actions")
    if not isinstance(actions, list):
        raise ValueError("proposal.proposed_actions must be a list")

    allowed = set(scenario["solution_contract"]["allowed_actions"])
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"proposal.proposed_actions[{index}] must be an object")
        action_type = action.get("type")
        if action_type not in allowed:
            raise ValueError(f"unsupported proposed action type: {action_type}")
        if not isinstance(action.get("params"), dict):
            raise ValueError(f"proposal.proposed_actions[{index}].params must be an object")
        if not isinstance(action.get("reason"), str) or not action["reason"].strip():
            raise ValueError(f"proposal.proposed_actions[{index}].reason must be a non-empty string")
