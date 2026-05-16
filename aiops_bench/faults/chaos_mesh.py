from __future__ import annotations

import time
from typing import Any

import yaml

from aiops_bench.environment.k8s import run_kubectl


CHAOS_NAMESPACE = "chaos-mesh"


class ChaosMeshManifestInjector:
    """基于 Chaos Mesh manifest 的故障注入器。"""

    def __init__(self, fault_type: str, crd: str, resource: str, builder: Any, verifier: Any) -> None:
        self.type = fault_type
        self.crd = crd
        self.resource = resource
        self.builder = builder
        self.verifier = verifier

    def inject(self, fault: dict[str, Any]) -> dict[str, Any]:
        """构造、应用并验证 Chaos Mesh 故障。"""
        ensure_crd(self.crd)
        name = chaos_resource_name(fault["id"])
        manifest = self.builder(name, fault)
        return apply_chaos_manifest(fault, name, self.resource, manifest, self.verifier)

    def cleanup(self, handle: dict[str, Any]) -> dict[str, Any]:
        """删除 Chaos Mesh 故障资源。"""
        result = run_kubectl(
            [
                "delete",
                handle["resource"],
                handle["name"],
                "-n",
                handle["namespace"],
                "--ignore-not-found=true",
            ],
            check=False,
        )
        return {
            "id": handle["id"],
            "type": handle["type"],
            "name": handle["name"],
            "namespace": handle["namespace"],
            "status": "deleted" if result["returncode"] == 0 else "failed",
            "command": result["command"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }


def default_chaos_mesh_injectors() -> list[ChaosMeshManifestInjector]:
    """返回内置 Chaos Mesh 故障注入器。"""
    return [
        ChaosMeshManifestInjector(
            "chaos_mesh.stress_cpu",
            "stresschaos.chaos-mesh.org",
            "stresschaos",
            build_stress_cpu_manifest,
            verify_stresschaos,
        ),
        ChaosMeshManifestInjector(
            "chaos_mesh.stress_memory",
            "stresschaos.chaos-mesh.org",
            "stresschaos",
            build_stress_memory_manifest,
            verify_stresschaos,
        ),
        ChaosMeshManifestInjector(
            "chaos_mesh.network_delay",
            "networkchaos.chaos-mesh.org",
            "networkchaos",
            build_network_delay_manifest,
            verify_networkchaos,
        ),
        ChaosMeshManifestInjector(
            "chaos_mesh.network_loss",
            "networkchaos.chaos-mesh.org",
            "networkchaos",
            build_network_loss_manifest,
            verify_networkchaos,
        ),
        ChaosMeshManifestInjector(
            "chaos_mesh.pod_kill",
            "podchaos.chaos-mesh.org",
            "podchaos",
            build_pod_kill_manifest,
            verify_podchaos,
        ),
    ]


def apply_chaos_manifest(
    fault: dict[str, Any],
    name: str,
    resource: str,
    manifest: dict[str, Any],
    verifier: Any,
) -> dict[str, Any]:
    """应用 Chaos Mesh manifest 并返回统一 handle。"""
    manifest_yaml = yaml.safe_dump(manifest, sort_keys=False)
    result = run_kubectl(["apply", "-f", "-"], input_text=manifest_yaml)
    verification = verifier(name, CHAOS_NAMESPACE)
    return {
        "id": fault["id"],
        "type": fault["type"],
        "name": name,
        "namespace": CHAOS_NAMESPACE,
        "resource": resource,
        "status": verification["status"],
        "command": result["command"],
        "stdout": result["stdout"],
        "manifest": manifest,
        "verification": verification,
    }


def ensure_crd(name: str) -> None:
    """确认当前集群已安装指定 CRD。"""
    run_kubectl(["get", "crd", name])


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


def build_stress_memory_manifest(name: str, fault: dict[str, Any]) -> dict[str, Any]:
    """构造 Chaos Mesh memory StressChaos manifest。"""
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
                "memory": {
                    "workers": int(spec["workers"]),
                    "size": str(spec["size"]),
                }
            },
            "duration": str(spec["duration"]),
        },
    }


def build_network_delay_manifest(name: str, fault: dict[str, Any]) -> dict[str, Any]:
    """构造 Chaos Mesh NetworkChaos delay manifest。"""
    target = fault["target"]
    spec = fault["spec"]
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {
            "name": name,
            "namespace": CHAOS_NAMESPACE,
        },
        "spec": {
            "action": "delay",
            "mode": spec.get("mode", "one"),
            "selector": {
                "namespaces": [target["namespace"]],
                "labelSelectors": target["selector"],
            },
            "delay": {
                "latency": str(spec["latency"]),
                "correlation": str(spec.get("correlation", "0")),
                "jitter": str(spec.get("jitter", "0ms")),
            },
            "duration": str(spec["duration"]),
        },
    }


def build_network_loss_manifest(name: str, fault: dict[str, Any]) -> dict[str, Any]:
    """构造 Chaos Mesh NetworkChaos loss manifest。"""
    target = fault["target"]
    spec = fault["spec"]
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {
            "name": name,
            "namespace": CHAOS_NAMESPACE,
        },
        "spec": {
            "action": "loss",
            "mode": spec.get("mode", "one"),
            "selector": {
                "namespaces": [target["namespace"]],
                "labelSelectors": target["selector"],
            },
            "loss": {
                "loss": str(spec["loss"]),
                "correlation": str(spec.get("correlation", "0")),
            },
            "duration": str(spec["duration"]),
        },
    }


def build_pod_kill_manifest(name: str, fault: dict[str, Any]) -> dict[str, Any]:
    """构造 Chaos Mesh PodChaos pod-kill manifest。"""
    target = fault["target"]
    spec = fault["spec"]
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "PodChaos",
        "metadata": {
            "name": name,
            "namespace": CHAOS_NAMESPACE,
        },
        "spec": {
            "action": "pod-kill",
            "mode": spec.get("mode", "one"),
            "selector": {
                "namespaces": [target["namespace"]],
                "labelSelectors": target["selector"],
            },
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


def verify_networkchaos(
    name: str,
    namespace: str,
    attempts: int = 8,
    interval_seconds: float = 1.0,
) -> dict[str, Any]:
    """验证 NetworkChaos 资源是否已创建并可被 Chaos Mesh 接收。"""
    last: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        result = run_kubectl(["get", "networkchaos", name, "-n", namespace, "-o", "yaml"], check=False)
        verification = parse_networkchaos_verification(result)
        verification["attempt"] = attempt
        last = verification
        if verification["status"] in {"active", "failed"}:
            return verification
        if attempt < attempts:
            time.sleep(interval_seconds)
    return last or {
        "status": "unknown",
        "failure_reason": "networkchaos verification did not run",
        "conditions": {},
        "records": [],
    }


def verify_podchaos(
    name: str,
    namespace: str,
    attempts: int = 8,
    interval_seconds: float = 1.0,
) -> dict[str, Any]:
    """验证 PodChaos 资源是否已创建并可被 Chaos Mesh 接收。"""
    last: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        result = run_kubectl(["get", "podchaos", name, "-n", namespace, "-o", "yaml"], check=False)
        verification = parse_podchaos_verification(result)
        verification["attempt"] = attempt
        last = verification
        if verification["status"] in {"active", "failed"}:
            return verification
        if attempt < attempts:
            time.sleep(interval_seconds)
    return last or {
        "status": "unknown",
        "failure_reason": "podchaos verification did not run",
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
    failed_messages = [
        event["message"]
        for record in records
        for event in record["events"]
        if event["type"] == "Failed"
    ]

    derived_status, status_reason, failure_reason = derive_chaos_status(
        "StressChaos",
        conditions,
        records,
        failed_messages,
    )

    return {
        "status": derived_status,
        "status_reason": status_reason,
        "failure_reason": failure_reason,
        "conditions": conditions,
        "records": records,
        "command": result["command"],
    }


def parse_networkchaos_verification(result: dict[str, Any]) -> dict[str, Any]:
    """解析 NetworkChaos 状态；网络类故障以资源存在和失败事件为主要判定。"""
    if result["returncode"] != 0:
        return {
            "status": "unknown",
            "failure_reason": result["stderr"] or "failed to read networkchaos",
            "conditions": {},
            "records": [],
            "command": result["command"],
        }

    try:
        data = yaml.safe_load(result["stdout"]) or {}
    except yaml.YAMLError as exc:
        return {
            "status": "unknown",
            "failure_reason": f"failed to parse networkchaos yaml: {exc}",
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
    failed_messages = [
        event["message"]
        for record in records
        for event in record["events"]
        if event["type"] == "Failed"
    ]
    derived_status, status_reason, failure_reason = derive_chaos_status(
        "NetworkChaos",
        conditions,
        records,
        failed_messages,
    )
    return {
        "status": derived_status,
        "status_reason": status_reason,
        "failure_reason": failure_reason,
        "conditions": conditions,
        "records": records,
        "command": result["command"],
    }


def parse_podchaos_verification(result: dict[str, Any]) -> dict[str, Any]:
    """解析 PodChaos 状态；pod-kill 以资源存在和失败事件为主要判定。"""
    return parse_existence_based_chaos_verification(result, "podchaos")


def parse_existence_based_chaos_verification(result: dict[str, Any], resource: str) -> dict[str, Any]:
    """解析状态较轻的 Chaos Mesh 资源。"""
    if result["returncode"] != 0:
        return {
            "status": "unknown",
            "failure_reason": result["stderr"] or f"failed to read {resource}",
            "conditions": {},
            "records": [],
            "command": result["command"],
        }

    try:
        data = yaml.safe_load(result["stdout"]) or {}
    except yaml.YAMLError as exc:
        return {
            "status": "unknown",
            "failure_reason": f"failed to parse {resource} yaml: {exc}",
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
    failed_messages = [
        event["message"]
        for record in records
        for event in record["events"]
        if event["type"] == "Failed"
    ]
    derived_status, status_reason, failure_reason = derive_chaos_status(
        resource,
        conditions,
        records,
        failed_messages,
    )
    return {
        "status": derived_status,
        "status_reason": status_reason,
        "failure_reason": failure_reason,
        "conditions": conditions,
        "records": records,
        "command": result["command"],
    }


def derive_chaos_status(
    resource: str,
    conditions: dict[str, Any],
    records: list[dict[str, Any]],
    failed_messages: list[str],
) -> tuple[str, str, str]:
    """根据 Chaos Mesh status 推导统一故障状态。"""
    injected_count = sum(record["injected_count"] for record in records)
    if conditions.get("AllInjected") == "True":
        return "active", "Chaos Mesh condition AllInjected=True", ""
    if injected_count > 0:
        return "active", "containerRecords show injected_count > 0", ""
    if failed_messages:
        return "failed", "Chaos Mesh reported failed events", failed_messages[0]
    if conditions.get("Selected") == "True":
        return "selected", "Chaos Mesh selected targets but injection is not confirmed yet", ""
    return "created", f"{resource} exists but injection is not confirmed yet", ""


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
