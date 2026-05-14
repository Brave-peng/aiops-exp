from __future__ import annotations

from typing import Any

from aiops_bench.actions import render_action_contract, validate_proposal_actions
from aiops_bench.agents.manual import build_agent_prompt
from aiops_bench.llm.deepseek import build_agent_metadata, chat_json, read_model
from aiops_bench.observability import render_observations_markdown


AGENT_ROLE = "proposal_agent"

SYSTEM_PROMPT = """你是 AIOps Benchmark 的“建议 Agent”。
你的任务是基于 Kubernetes 现场证据诊断问题，并提出安全、可执行、符合动作约束的修复建议。
你只能提出修复建议，不能声称已经执行修复。
不要使用未被现场证据支持的结论。
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
        + "所有自然语言字段必须使用中文。\n"
        + "status 必须为 ready。proposed_actions 里的 type 必须来自允许动作类型。\n"
        + "动作参数必须符合契约：\n"
        + render_action_contract(scenario["solution_contract"]["allowed_actions"])
        + "\n"
        + "evidence 中必须引用现场中能核对的 Kubernetes 状态、Chaos Mesh 条件或命令输出。\n"
    )


def solve_with_deepseek_agent(
    scenario: dict[str, Any],
    observations: dict[str, Any],
) -> dict[str, Any]:
    """调用 DeepSeek 生成修复建议。"""
    prompt = build_deepseek_proposal_prompt(scenario, observations)
    model = read_model("AIOPS_DEEPSEEK_PROPOSER_MODEL")
    proposal = chat_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt, model=model)
    proposal.setdefault("status", "ready")
    proposal["agent"] = build_agent_metadata(AGENT_ROLE, model)
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
    validate_proposal_actions(scenario, proposal)
