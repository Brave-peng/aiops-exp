from __future__ import annotations

from typing import Any

from aiops_bench.observability.kubernetes import trim_text


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

    workload = observations.get("summary", {}).get("workload") or {}
    if workload:
        lines.extend(
            [
                "### Workload",
                "",
                f"- resource: `{str(workload.get('kind', '')).lower()}/{workload.get('name', '')}`",
                f"- namespace: `{workload.get('namespace', '')}`",
                f"- selector: `{workload.get('selector', {})}`",
                "",
            ]
        )

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

    evidence_items = observations.get("evidence_items", [])
    if evidence_items:
        lines.extend(["## 标准化证据", ""])
        for item in evidence_items[:30]:
            lines.extend(
                [
                    f"### `{item.get('id', '')}`",
                    "",
                    f"- source: `{item.get('source', '')}`",
                    f"- signal_type: `{item.get('signal_type', '')}`",
                    f"- subject: `{item.get('subject', '')}`",
                    f"- summary: {trim_text(item.get('summary') or '<none>', 600)}",
                    f"- raw_ref: `{item.get('raw_ref', '')}`",
                    f"- confidence: `{item.get('confidence', '')}`",
                    "",
                ]
            )
        if len(evidence_items) > 30:
            lines.extend([f"... 还有 {len(evidence_items) - 30} 条证据，详见 observations.json", ""])

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
