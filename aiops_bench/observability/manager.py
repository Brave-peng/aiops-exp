from __future__ import annotations

from typing import Any

from aiops_bench.observability.base import ObservationSource
from aiops_bench.observability.kubernetes import KubernetesObservationSource
from aiops_bench.scenario import get_workload


def collect_observations(scenario: dict[str, Any], fault_handles: list[dict[str, Any]]) -> dict[str, Any]:
    """采集现场快照，供 proposer 和 judge 使用。"""
    namespace = scenario["environment"]["namespace"]
    source_results = [source.collect(scenario, fault_handles) for source in build_observation_sources(scenario)]
    commands = [command for result in source_results for command in result.get("commands", [])]
    evidence_items = [evidence for result in source_results for evidence in result.get("evidence_items", [])]
    return {
        "namespace": namespace,
        "summary": build_observation_summary(namespace, fault_handles, get_workload(scenario)),
        "commands": commands,
        "evidence_items": evidence_items,
    }


def build_observation_sources(scenario: dict[str, Any]) -> list[ObservationSource]:
    """根据 scenario 构造观测数据源。"""
    configured = scenario.get("observability", {}).get("sources") or [{"type": "kubernetes"}]
    sources: list[ObservationSource] = []
    for item in configured:
        source_type = item.get("type") if isinstance(item, dict) else None
        if source_type == "kubernetes":
            sources.append(KubernetesObservationSource())
        else:
            raise ValueError(f"unsupported observation source type: {source_type}")
    return sources


def build_observation_summary(
    namespace: str,
    fault_handles: list[dict[str, Any]],
    workload: dict[str, Any],
) -> dict[str, Any]:
    """构造机器可读摘要，避免 judge 从长 YAML 里猜关键状态。"""
    return {
        "namespace": namespace,
        "workload": workload,
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
