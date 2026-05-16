from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ScenarioError(ValueError):
    """场景文件不合法时抛出的错误。"""


@dataclass(frozen=True)
class ScenarioContext:
    """场景数据和运行时路径上下文。"""

    data: dict[str, Any]
    path: Path
    project_root: Path

    def resolve_path(self, value: str | Path) -> Path:
        """解析场景里的相对路径。"""
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return self.project_root / candidate


def validate_scenario(data: dict[str, Any]) -> None:
    """检查运行器需要的字段。"""
    required = [
        "id",
        "name",
        "environment",
        "workload",
        "faults",
        "agent_task",
        "solution_contract",
        "evaluation",
    ]
    for key in required:
        if not data.get(key):
            raise ScenarioError(f"missing required field: {key}")

    validate_environment(data["environment"])
    validate_workload(data["workload"])
    validate_faults(data["faults"])
    validate_agent_task(data["agent_task"])
    validate_solution_contract(data["solution_contract"])
    validate_evaluation(data["evaluation"])


def validate_environment(environment: Any) -> None:
    """校验 Kubernetes 环境描述。"""
    if not isinstance(environment, dict):
        raise ScenarioError("environment must be an object")
    for key in ["type", "namespace", "setup", "readiness", "cleanup"]:
        if not environment.get(key):
            raise ScenarioError(f"missing required field: environment.{key}")
    if environment["type"] != "k8s":
        raise ScenarioError("environment.type must be 'k8s'")
    if not isinstance(environment["setup"], list) or not environment["setup"]:
        raise ScenarioError("environment.setup must be a non-empty list")
    if not isinstance(environment["readiness"], list) or not environment["readiness"]:
        raise ScenarioError("environment.readiness must be a non-empty list")
    if not isinstance(environment["cleanup"], dict):
        raise ScenarioError("environment.cleanup must be an object")


def validate_workload(workload: Any) -> None:
    """校验被观测和诊断的 workload。"""
    if not isinstance(workload, dict):
        raise ScenarioError("workload must be an object")
    for key in ("namespace", "kind", "name"):
        value = workload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ScenarioError(f"workload.{key} must be a non-empty string")
    selector = workload.get("selector")
    if not isinstance(selector, dict) or not selector:
        raise ScenarioError("workload.selector must be a non-empty object")
    if not all(isinstance(key, str) and key and isinstance(value, str) and value for key, value in selector.items()):
        raise ScenarioError("workload.selector must only contain non-empty string keys and values")
    containers = workload.get("containers")
    if containers is not None:
        if not isinstance(containers, list) or not all(isinstance(item, str) and item for item in containers):
            raise ScenarioError("workload.containers must only contain non-empty strings")


def validate_faults(faults: Any) -> None:
    """校验故障列表。"""
    if not isinstance(faults, list) or not faults:
        raise ScenarioError("faults must be a non-empty list")
    for index, fault in enumerate(faults):
        if not isinstance(fault, dict):
            raise ScenarioError(f"faults[{index}] must be an object")
        for key in ["id", "type", "target", "spec"]:
            if not fault.get(key):
                raise ScenarioError(f"missing required field: faults[{index}].{key}")
        if not isinstance(fault["target"], dict):
            raise ScenarioError(f"faults[{index}].target must be an object")
        if not isinstance(fault["spec"], dict):
            raise ScenarioError(f"faults[{index}].spec must be an object")


def validate_agent_task(agent_task: Any) -> None:
    """校验 Agent 作答要求。"""
    if not isinstance(agent_task, dict):
        raise ScenarioError("agent_task must be an object")
    if not isinstance(agent_task.get("instruction"), str) or not agent_task["instruction"].strip():
        raise ScenarioError("agent_task.instruction must be a non-empty string")


def validate_solution_contract(solution_contract: Any) -> None:
    """校验建议动作契约。"""
    if not isinstance(solution_contract, dict):
        raise ScenarioError("solution_contract must be an object")
    allowed_actions = solution_contract.get("allowed_actions")
    if not isinstance(allowed_actions, list) or not allowed_actions:
        raise ScenarioError("solution_contract.allowed_actions must be a non-empty list")
    if not all(isinstance(action, str) and action for action in allowed_actions):
        raise ScenarioError("solution_contract.allowed_actions must only contain non-empty strings")


def validate_evaluation(evaluation: Any) -> None:
    """校验评估配置。"""
    if not isinstance(evaluation, dict):
        raise ScenarioError("evaluation must be an object")
    if not isinstance(evaluation.get("type"), str) or not evaluation["type"].strip():
        raise ScenarioError("evaluation.type must be a non-empty string")


def get_workload(data: dict[str, Any]) -> dict[str, Any]:
    """返回标准化 workload。"""
    workload = data["workload"]
    return {
        "namespace": workload["namespace"],
        "kind": workload["kind"],
        "name": workload["name"],
        "selector": dict(workload["selector"]),
        "containers": list(workload.get("containers") or [workload["name"]]),
    }
