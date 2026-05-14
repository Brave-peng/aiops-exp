from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def create_run_dir(scenario_id: str, results_root: str | Path = "results") -> Path:
    """创建本次实验的结果目录。"""
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(results_root) / scenario_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_run_files(
    run_dir: Path,
    scenario: dict[str, Any],
    agent_prompt: str,
    evaluation_prompt: str,
    observations: dict[str, Any],
    observations_markdown: str,
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    """写入本次实验的结果文件。"""
    write_yaml(run_dir / "scenario.yaml", scenario)
    write_json(run_dir / "observations.json", observations)
    write_json(
        run_dir / "run.json",
        build_run_artifact(summary, agent_prompt, evaluation_prompt, proposal, evaluation),
    )
    write_report(
        run_dir,
        scenario,
        summary,
        proposal,
        evaluation,
        observations,
        agent_prompt=agent_prompt,
        observations_markdown=observations_markdown,
    )


def build_run_artifact(
    summary: dict[str, Any],
    agent_prompt: str,
    evaluation_prompt: str,
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """构造单文件机器可读结果，减少结果目录里的文件数量。"""
    artifact = dict(summary)
    artifact["proposal"] = proposal
    artifact["evaluation"] = evaluation
    artifact["prompts"] = {
        "agent": agent_prompt,
        "evaluation": evaluation_prompt,
    }
    return artifact


def write_report(
    run_dir: Path,
    scenario: dict[str, Any],
    summary: dict[str, Any],
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    observations: dict[str, Any],
    *,
    cleanup: dict[str, Any] | None = None,
    agent_prompt: str = "",
    observations_markdown: str = "",
) -> None:
    """写入中文优先的人类可读报告。"""
    lines = [
        f"# 运行报告：{scenario['id']}",
        "",
        "## 结论",
        "",
        f"- 总体结果：{verdict_text(summary, evaluation)}",
        f"- 场景：{scenario.get('name', scenario['id'])}",
        f"- 运行目录：`{summary.get('run_dir', run_dir)}`",
        f"- Proposer：`{summary.get('proposer', '')}`",
        f"- Judge：`{summary.get('judge', '')}`",
        "",
        "## 阶段状态",
        "",
        f"- 环境准备：{status_text((summary.get('environment') or {}).get('status'))}",
        f"- 故障注入：{faults_status_text(summary.get('faults', []))}",
        f"- 观测采集：{status_text(summary.get('observations_status'))}",
        f"- 建议生成：{status_text(summary.get('proposal_status'))}",
        f"- 评估结果：{status_text(summary.get('evaluation_status'))}",
    ]
    if cleanup is not None:
        lines.append(f"- 清理结果：{cleanup_status_text(cleanup)}")

    lines.extend(["", "## 故障注入", ""])
    faults = observations.get("summary", {}).get("faults") or summary.get("faults", [])
    if faults:
        for fault in faults:
            lines.extend(render_fault_lines(fault))
    else:
        lines.append("- 未采集到故障摘要。")

    lines.extend(["", "## Agent 建议", ""])
    proposal_agent = proposal.get("agent")
    if proposal_agent:
        lines.extend(render_agent_lines("建议 Agent", proposal_agent))
    lines.extend(render_proposal_lines(proposal))

    lines.extend(["", "## 评估", ""])
    evaluation_agent = evaluation.get("agent")
    if evaluation_agent:
        lines.extend(render_agent_lines("评估 Agent", evaluation_agent))
    lines.extend(render_evaluation_lines(evaluation))

    warnings = collect_warnings(summary, observations, evaluation, cleanup)
    if warnings:
        lines.extend(["", "## 注意事项", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(
        [
            "",
            "## 结果文件",
            "",
            "- `report.md`：中文可读报告",
            "- `run.json`：完整结构化结果，包含建议、评估和提示词",
            "- `observations.json`：原始观测命令输出",
            "- `scenario.yaml`：本次运行使用的场景快照",
        ]
    )
    if cleanup is not None:
        lines.append("- `cleanup.json`：清理动作结果")

    if proposal.get("status") == "pending" and agent_prompt:
        lines.extend(["", "## 人工处理提示词", "", "````markdown", agent_prompt.rstrip(), "````"])

    (run_dir / "report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def verdict_text(summary: dict[str, Any], evaluation: dict[str, Any]) -> str:
    """返回面向人的总体结论。"""
    run_status = summary.get("run_status")
    evaluation_status = evaluation.get("status")
    if run_status == "completed" and evaluation_status == "passed":
        return "通过"
    if run_status == "completed" and evaluation_status == "pending":
        return "已完成，等待人工评估"
    if run_status == "invalid":
        return "无效运行"
    if run_status == "failed" or evaluation_status == "failed":
        return "失败"
    return status_text(run_status)


def status_text(value: Any) -> str:
    """把内部状态翻译成中文。"""
    mapping = {
        "active": "已生效",
        "applied": "已应用",
        "collected": "已采集",
        "completed": "已完成",
        "deleted": "已删除",
        "failed": "失败",
        "invalid": "无效",
        "not_collected": "未采集",
        "passed": "通过",
        "pending": "待处理",
        "ready": "就绪",
        "skipped": "已跳过",
        None: "未知",
    }
    return mapping.get(value, str(value))


def faults_status_text(faults: list[dict[str, Any]]) -> str:
    """汇总故障注入状态。"""
    if not faults:
        return "未执行"
    if all(fault.get("status") == "active" for fault in faults):
        return "已生效"
    if any(fault.get("status") == "failed" for fault in faults):
        return "失败"
    return "部分完成"


def cleanup_status_text(cleanup: dict[str, Any]) -> str:
    """汇总清理状态。"""
    if cleanup.get("errors"):
        return "清理有错误"
    environment = cleanup.get("environment") or {}
    faults = cleanup.get("faults") or []
    if environment.get("status") == "deleted" and all(fault.get("status") == "deleted" for fault in faults):
        return "已完成"
    return "部分完成"


def render_fault_lines(fault: dict[str, Any]) -> list[str]:
    """渲染单个故障摘要。"""
    verification = fault.get("verification", {})
    conditions = fault.get("conditions") or verification.get("conditions") or {}
    records = fault.get("records") or verification.get("records") or []
    lines = [
        f"- `{fault.get('id', '')}`：{status_text(fault.get('status'))}",
        f"  类型：`{fault.get('type', '')}`",
        f"  资源：`{fault.get('namespace', '')}/{fault.get('name', '')}`",
    ]
    status_reason = fault.get("status_reason") or verification.get("status_reason")
    if status_reason:
        lines.append(f"  判定依据：{status_reason}")
    if conditions:
        condition_text = "，".join(f"{key}={value}" for key, value in conditions.items())
        lines.append(f"  原始条件：{condition_text}")
    for record in records:
        lines.append(
            "  目标容器："
            f"`{record.get('id', '')}`，phase={record.get('phase', '')}，"
            f"injected={record.get('injected_count', 0)}"
        )
    failure_reason = fault.get("failure_reason") or verification.get("failure_reason")
    if failure_reason:
        lines.append(f"  失败原因：{failure_reason}")
    return lines


def render_proposal_lines(proposal: dict[str, Any]) -> list[str]:
    """渲染建议摘要。"""
    if not proposal:
        return ["- 未生成建议。"]
    lines: list[str] = []
    if proposal.get("status") == "pending":
        lines.append(f"- 状态：待人工处理。{proposal.get('message', '')}".rstrip())
        return lines
    if proposal.get("diagnosis"):
        lines.append(f"- 诊断：{proposal['diagnosis']}")
    evidence = proposal.get("evidence") or []
    if evidence:
        lines.append("- 依据：" + "；".join(str(item) for item in evidence))
    actions = proposal.get("proposed_actions") or []
    if actions:
        lines.append("- 建议动作：")
        for action in actions:
            lines.append(
                f"  - `{action.get('type', '')}`：{action.get('reason', '')} "
                f"参数 `{json.dumps(action.get('params', {}), ensure_ascii=False)}`"
            )
    if proposal.get("error"):
        lines.append(f"- 错误：{proposal['error'].get('message', '')}")
    return lines or ["- 建议为空。"]


def render_agent_lines(label: str, agent: dict[str, Any]) -> list[str]:
    """渲染 AI Agent 元数据。"""
    return [
        f"- {label}：`{agent.get('provider', '')}` / `{agent.get('model', '')}`",
    ]


def render_evaluation_lines(evaluation: dict[str, Any]) -> list[str]:
    """渲染评估摘要。"""
    if not evaluation:
        return ["- 未评估。"]
    lines = [f"- 状态：{status_text(evaluation.get('status'))}"]
    if "score" in evaluation:
        lines.append(f"- 分数：{evaluation['score']}")
    if evaluation.get("summary"):
        lines.append(f"- 摘要：{evaluation['summary']}")
    strengths = evaluation.get("strengths") or []
    if strengths:
        lines.append("- 优点：" + "；".join(str(item) for item in strengths))
    risks = evaluation.get("risks") or []
    if risks:
        lines.append("- 风险：" + "；".join(str(item) for item in risks))
    violations = evaluation.get("contract_violations") or []
    if violations:
        lines.append("- 契约问题：" + "；".join(str(item) for item in violations))
    if evaluation.get("recommendation"):
        lines.append(f"- 建议结论：{evaluation['recommendation']}")
    if evaluation.get("message"):
        lines.append(f"- 说明：{evaluation['message']}")
    if evaluation.get("error"):
        lines.append(f"- 错误：{evaluation['error'].get('message', '')}")
    return lines


def collect_warnings(
    summary: dict[str, Any],
    observations: dict[str, Any],
    evaluation: dict[str, Any],
    cleanup: dict[str, Any] | None,
) -> list[str]:
    """收集需要用户注意但不一定导致失败的问题。"""
    warnings: list[str] = []
    for item in observations.get("commands", []):
        command = " ".join(item.get("command", []))
        output = item.get("stderr") or item.get("stdout") or ""
        if item.get("returncode") != 0:
            warnings.append(f"`{command}` 执行失败：{output.strip() or '无输出'}")
    if summary.get("proposer") == "manual" or evaluation.get("status") == "pending":
        warnings.append("当前结果需要人工读取提示词并完成建议或评估，不代表自动诊断已通过。")
    if cleanup and cleanup.get("errors"):
        warnings.append(f"清理阶段存在错误：{json.dumps(cleanup['errors'], ensure_ascii=False)}")
    return warnings


def write_json(path: Path, data: Any) -> None:
    """写入易读 JSON。"""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: Any) -> None:
    """写入 YAML。"""
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
