from __future__ import annotations

from typing import Any

from aiops_bench.faults.base import FaultInjector
from aiops_bench.faults.chaos_mesh import default_chaos_mesh_injectors
from aiops_bench.faults.kubernetes import KubernetesSetEnvInjector


def default_fault_registry() -> dict[str, FaultInjector]:
    """构造默认故障注入器注册表。"""
    injectors: list[FaultInjector] = [
        *default_chaos_mesh_injectors(),
        KubernetesSetEnvInjector(),
    ]
    return {injector.type: injector for injector in injectors}


def inject_faults(
    faults: list[dict[str, Any]],
    registry: dict[str, FaultInjector] | None = None,
) -> list[dict[str, Any]]:
    """按注册表注入故障。"""
    active_registry = registry or default_fault_registry()
    handles: list[dict[str, Any]] = []
    try:
        for fault in faults:
            handles.append(inject_fault(fault, active_registry))
    except Exception:
        if handles:
            cleanup_faults(handles, active_registry)
        raise
    return handles


def inject_fault(
    fault: dict[str, Any],
    registry: dict[str, FaultInjector] | None = None,
) -> dict[str, Any]:
    """注入单个故障。"""
    active_registry = registry or default_fault_registry()
    fault_type = fault["type"]
    injector = active_registry.get(fault_type)
    if injector is None:
        raise ValueError(f"unsupported fault type: {fault_type}")
    return injector.inject(fault)


def cleanup_faults(
    handles: list[dict[str, Any]],
    registry: dict[str, FaultInjector] | None = None,
) -> list[dict[str, Any]]:
    """按注册表清理故障。"""
    active_registry = registry or default_fault_registry()
    cleanup_results: list[dict[str, Any]] = []
    for handle in handles:
        fault_type = handle["type"]
        injector = active_registry.get(fault_type)
        if injector is None:
            cleanup_results.append(
                {
                    "id": handle.get("id"),
                    "type": fault_type,
                    "name": handle.get("name"),
                    "namespace": handle.get("namespace"),
                    "status": "failed",
                    "stderr": f"unsupported fault type during cleanup: {fault_type}",
                }
            )
            continue
        cleanup_results.append(injector.cleanup(handle))
    return cleanup_results
