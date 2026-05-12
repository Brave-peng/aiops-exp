from __future__ import annotations

import time
from typing import Any

import yaml

from aiops_bench.environment.k8s import run_kubectl


CHAOS_NAMESPACE = "chaos-mesh"


def inject_faults(faults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """注入 Chaos Mesh 故障。"""
    ensure_stresschaos_crd()
    handles: list[dict[str, Any]] = []
    try:
        for fault in faults:
            handles.append(inject_fault(fault))
    except Exception:
        if handles:
            cleanup_faults(handles)
        raise
    return handles


def cleanup_faults(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清理已注入故障。"""
    cleanup_results: list[dict[str, Any]] = []
    for handle in handles:
        result = run_kubectl(
            [
                "delete",
                "stresschaos",
                handle["name"],
                "-n",
                handle["namespace"],
                "--ignore-not-found=true",
            ],
            check=False,
        )
        cleanup_results.append(
            {
                "id": handle["id"],
                "type": handle["type"],
                "name": handle["name"],
                "namespace": handle["namespace"],
                "status": "deleted" if result["returncode"] == 0 else "failed",
                "command": result["command"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            }
        )
    return cleanup_results


def inject_fault(fault: dict[str, Any]) -> dict[str, Any]:
    """注入一个支持的 Chaos Mesh 故障。"""
    fault_type = fault["type"]
    if fault_type != "chaos_mesh.stress_cpu":
        raise ValueError(f"unsupported fault type: {fault_type}")

    name = chaos_resource_name(fault["id"])
    manifest = build_stress_cpu_manifest(name, fault)
    manifest_yaml = yaml.safe_dump(manifest, sort_keys=False)
    result = run_kubectl(["apply", "-f", "-"], input_text=manifest_yaml)
    verification = verify_stresschaos(name, CHAOS_NAMESPACE)
    return {
        "id": fault["id"],
        "type": fault_type,
        "name": name,
        "namespace": CHAOS_NAMESPACE,
        "status": verification["status"],
        "command": result["command"],
        "stdout": result["stdout"],
        "manifest": manifest,
        "verification": verification,
    }


def ensure_stresschaos_crd() -> None:
    """确认当前集群已安装 StressChaos CRD。"""
    run_kubectl(["get", "crd", "stresschaos.chaos-mesh.org"])


def build_stress_cpu_manifest(name: str, fault: dict[str, Any]) -> dict[str, Any]:
    """构造 Chaos Mesh StressChaos manifest。"""
    target = fault["target"]
    spec = fault["spec"]
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "StressChaos",
        "metadata": {
            "name": name,
            "namespace": CHAOS_NAMESPACE,
        },
        "spec": {
            "mode": "one",
            "selector": {
                "namespaces": [target["namespace"]],
                "labelSelectors": target["selector"],
            },
            "stressors": {
                "cpu": {
                    "workers": int(spec["workers"]),
                    "load": int(spec["load"]),
                }
            },
            "duration": str(spec["duration"]),
        },
    }


def chaos_resource_name(fault_id: str) -> str:
    """将 fault id 映射成 Kubernetes 资源名。"""
    name = "aiops-" + "".join(char if char.isalnum() else "-" for char in fault_id.lower())
    return name.strip("-")


def verify_stresschaos(
    name: str,
    namespace: str,
    attempts: int = 8,
    interval_seconds: float = 1.0,
) -> dict[str, Any]:
    """验证 StressChaos 是否真实注入到目标容器。"""
    last: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        result = run_kubectl(["get", "stresschaos", name, "-n", namespace, "-o", "yaml"], check=False)
        verification = parse_stresschaos_verification(result)
        verification["attempt"] = attempt
        last = verification
        if verification["status"] in {"active", "failed"}:
            return verification
        if attempt < attempts:
            time.sleep(interval_seconds)
    return last or {
        "status": "unknown",
        "failure_reason": "stresschaos verification did not run",
        "conditions": {},
        "records": [],
    }


def parse_stresschaos_verification(result: dict[str, Any]) -> dict[str, Any]:
    """解析 StressChaos status，区分 CRD 创建和真实注入状态。"""
    if result["returncode"] != 0:
        return {
            "status": "unknown",
            "failure_reason": result["stderr"] or "failed to read stresschaos",
            "conditions": {},
            "records": [],
            "command": result["command"],
        }

    try:
        data = yaml.safe_load(result["stdout"]) or {}
    except yaml.YAMLError as exc:
        return {
            "status": "unknown",
            "failure_reason": f"failed to parse stresschaos yaml: {exc}",
            "conditions": {},
            "records": [],
            "command": result["command"],
        }

    status = data.get("status") or {}
    conditions = {
        item.get("type"): item.get("status")
        for item in status.get("conditions", [])
        if isinstance(item, dict) and item.get("type")
    }
    records = summarize_container_records(status.get("experiment", {}).get("containerRecords", []))
    injected_count = sum(record["injected_count"] for record in records)
    failed_messages = [
        event["message"]
        for record in records
        for event in record["events"]
        if event["type"] == "Failed"
    ]

    if conditions.get("AllInjected") == "True" or injected_count > 0:
        derived_status = "active"
    elif failed_messages:
        derived_status = "failed"
    elif conditions.get("Selected") == "True":
        derived_status = "selected"
    else:
        derived_status = "created"

    return {
        "status": derived_status,
        "failure_reason": failed_messages[0] if failed_messages else "",
        "conditions": conditions,
        "records": records,
        "command": result["command"],
    }


def summarize_container_records(records: Any) -> list[dict[str, Any]]:
    """提取 containerRecords 中对注入判定有用的字段。"""
    if not isinstance(records, list):
        return []
    summary: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        events = []
        for event in record.get("events", []):
            if not isinstance(event, dict):
                continue
            events.append(
                {
                    "type": str(event.get("type", "")),
                    "operation": str(event.get("operation", "")),
                    "message": str(event.get("message", "")),
                }
            )
        summary.append(
            {
                "id": str(record.get("id", "")),
                "phase": str(record.get("phase", "")),
                "injected_count": int(record.get("injectedCount") or 0),
                "recovered_count": int(record.get("recoveredCount") or 0),
                "events": events,
            }
        )
    return summary
