from __future__ import annotations

from typing import Any

from aiops_bench.environment.k8s import run_kubectl


def collect_observations(scenario: dict[str, Any], fault_handles: list[dict[str, Any]]) -> dict[str, Any]:
    """采集一组只读 Kubernetes 现场快照，供 proposer 和 judge 使用。"""
    namespace = scenario["environment"]["namespace"]
    commands = [
        ["get", "deploy,po,svc", "-n", namespace, "-o", "wide"],
        ["describe", "deployment/demo-service", "-n", namespace],
        ["logs", "deployment/demo-service", "-n", namespace, "--tail=100"],
        ["top", "pod", "-n", namespace],
    ]
    for handle in fault_handles:
        if handle.get("type") == "chaos_mesh.stress_cpu":
            commands.extend(
                [
                    ["get", "stresschaos", handle["name"], "-n", handle["namespace"], "-o", "yaml"],
                    ["describe", "stresschaos", handle["name"], "-n", handle["namespace"]],
                ]
            )

    return {
        "namespace": namespace,
        "summary": build_observation_summary(namespace, fault_handles),
        "commands": [
            {
                "command": result["command"],
                "returncode": result["returncode"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            }
            for result in (run_kubectl(args, check=False) for args in commands)
        ],
    }


def build_observation_summary(namespace: str, fault_handles: list[dict[str, Any]]) -> dict[str, Any]:
    """构造机器可读摘要，避免 judge 从长 YAML 里猜关键状态。"""
    return {
        "namespace": namespace,
        "faults": [
            {
                "id": handle.get("id"),
                "type": handle.get("type"),
                "name": handle.get("name"),
                "namespace": handle.get("namespace"),
                "status": handle.get("status"),
                "status_reason": handle.get("verification", {}).get("status_reason", ""),
                "failure_reason": handle.get("verification", {}).get("failure_reason", ""),
                "conditions": handle.get("verification", {}).get("conditions", {}),
                "records": handle.get("verification", {}).get("records", []),
            }
            for handle in fault_handles
        ],
    }


def render_observations_markdown(observations: dict[str, Any]) -> str:
    """把现场快照渲染为人可读 Markdown。"""
    lines = [
        "# Kubernetes 观测",
        "",
        f"- namespace: `{observations.get('namespace', '')}`",
        "",
        "## 摘要",
        "",
    ]

    faults = observations.get("summary", {}).get("faults", [])
    if faults:
        for fault in faults:
            lines.extend(
                [
                    f"### 故障 `{fault.get('id', '')}`",
                    "",
                    f"- type: `{fault.get('type', '')}`",
                    f"- resource: `{fault.get('namespace', '')}/{fault.get('name', '')}`",
                    f"- status: `{fault.get('status', '')}`",
                    f"- status_reason: {trim_text(fault.get('status_reason') or '<none>', 600)}",
                    f"- failure_reason: {trim_text(fault.get('failure_reason') or '<none>', 600)}",
                    f"- conditions: `{fault.get('conditions', {})}`",
                    "",
                ]
            )
            records = fault.get("records", [])
            if records:
                lines.extend(["#### 容器记录", ""])
                for record in records:
                    lines.extend(
                        [
                            f"- id: `{record.get('id', '')}`",
                            f"  phase: `{record.get('phase', '')}`",
                            f"  injected_count: `{record.get('injected_count', 0)}`",
                            f"  recovered_count: `{record.get('recovered_count', 0)}`",
                        ]
                    )
                    failed_events = [
                        event
                        for event in record.get("events", [])
                        if event.get("type") == "Failed"
                    ]
                    if failed_events:
                        lines.append("  failed_events:")
                        for event in failed_events[:3]:
                            lines.append(f"  - {trim_text(event.get('message', ''), 500)}")
                    lines.append("")
    else:
        lines.extend(["未采集到故障摘要。", ""])

    lines.extend(["## 命令输出", ""])
    for item in observations.get("commands", []):
        command = " ".join(item["command"])
        output = trim_command_output(item.get("stdout") or item.get("stderr") or "<empty>")
        lines.extend(
            [
                f"### `{command}`",
                "",
                f"- returncode: `{item['returncode']}`",
                "",
                "```text",
                output,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def trim_command_output(value: str, max_lines: int = 120, max_chars: int = 12000) -> str:
    """限制 Markdown 中的长命令输出；完整输出仍保留在 observations.json。"""
    lines = value.splitlines()
    trimmed = "\n".join(lines[:max_lines])
    truncated = len(lines) > max_lines
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rstrip()
        truncated = True
    if truncated:
        trimmed += "\n... <truncated; see observations.json for full output>"
    return trimmed


def trim_text(value: str, max_chars: int) -> str:
    """限制摘要里的单行长错误。"""
    value = " ".join(value.split())
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."
