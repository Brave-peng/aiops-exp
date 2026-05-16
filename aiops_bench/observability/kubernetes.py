from __future__ import annotations

from typing import Any

from aiops_bench.environment.k8s import run_kubectl
from aiops_bench.scenario import get_workload


class KubernetesObservationSource:
    """默认 Kubernetes 观测数据源。"""

    type = "kubernetes"

    def collect(self, scenario: dict[str, Any], fault_handles: list[dict[str, Any]]) -> dict[str, Any]:
        """采集 Kubernetes 命令快照和标准证据项。"""
        namespace = scenario["environment"]["namespace"]
        workload = get_workload(scenario)
        commands = build_kubernetes_commands(namespace, fault_handles, workload)
        command_results = [
            {
                "command": result["command"],
                "returncode": result["returncode"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            }
            for result in (run_kubectl(args, check=False) for args in commands)
        ]
        return {
            "commands": command_results,
            "evidence_items": build_kubernetes_evidence_items(namespace, fault_handles, command_results),
        }


def build_kubernetes_commands(
    namespace: str,
    fault_handles: list[dict[str, Any]],
    workload: dict[str, Any],
) -> list[list[str]]:
    """构造 Kubernetes 只读采集命令。"""
    workload_namespace = str(workload["namespace"])
    selector = format_label_selector(workload["selector"])
    commands = [
        ["get", "deploy,po,svc", "-n", namespace, "-o", "wide"],
        ["describe", workload_resource(workload), "-n", workload_namespace],
        ["logs", "-l", selector, "-n", workload_namespace, "--all-containers=true", "--tail=100"],
        ["top", "pod", "-n", workload_namespace],
    ]
    for handle in fault_handles:
        resource = handle.get("resource")
        if resource in {"stresschaos", "networkchaos", "podchaos"}:
            commands.extend(
                [
                    ["get", resource, handle["name"], "-n", handle["namespace"], "-o", "yaml"],
                    ["describe", resource, handle["name"], "-n", handle["namespace"]],
                ]
            )
    return commands


def build_kubernetes_evidence_items(
    namespace: str,
    fault_handles: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """把 Kubernetes 观测归一成证据项，供后续多源上下文复用。"""
    items: list[dict[str, Any]] = []
    for handle in fault_handles:
        verification = handle.get("verification", {})
        items.append(
            {
                "id": f"fault:{handle.get('id', '')}",
                "source": "kubernetes",
                "signal_type": "fault",
                "subject": f"{handle.get('namespace', namespace)}/{handle.get('name', '')}",
                "summary": verification.get("status_reason") or f"fault status is {handle.get('status', '')}",
                "raw_ref": handle.get("command", ""),
                "confidence": 0.9 if handle.get("status") == "active" else 0.5,
                "attributes": {
                    "fault_type": handle.get("type"),
                    "status": handle.get("status"),
                    "failure_reason": verification.get("failure_reason", ""),
                    "conditions": verification.get("conditions", {}),
                },
            }
        )
    for index, command in enumerate(commands):
        items.append(
            {
                "id": f"kubernetes-command:{index + 1}",
                "source": "kubernetes",
                "signal_type": "command",
                "subject": namespace,
                "summary": summarize_command_result(command),
                "raw_ref": " ".join(command.get("command", [])),
                "confidence": 0.8 if command.get("returncode") == 0 else 0.4,
                "attributes": {
                    "returncode": command.get("returncode"),
                    "stderr": trim_text(command.get("stderr") or "", 500),
                },
            }
        )
    return items


def workload_resource(workload: dict[str, Any]) -> str:
    """把 workload 描述转成 kubectl resource/name。"""
    return f"{str(workload['kind']).strip().lower()}/{workload['name']}"


def format_label_selector(selector: dict[str, str]) -> str:
    """把 selector 字典转成 kubectl -l 参数。"""
    return ",".join(f"{key}={value}" for key, value in selector.items())


def summarize_command_result(command: dict[str, Any]) -> str:
    """生成命令输出证据摘要。"""
    raw_command = " ".join(command.get("command", []))
    if command.get("returncode") != 0:
        return f"命令 `{raw_command}` 执行失败：{trim_text(command.get('stderr') or '<empty>', 300)}"
    stdout = command.get("stdout") or ""
    first_line = stdout.splitlines()[0] if stdout.splitlines() else "<empty>"
    return f"命令 `{raw_command}` 成功，首行输出：{trim_text(first_line, 300)}"


def trim_text(value: str, max_chars: int) -> str:
    """限制摘要里的单行长错误。"""
    value = " ".join(value.split())
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."
