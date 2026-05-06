from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ScenarioError(ValueError):
    """场景文件不合法时抛出的错误。"""

    pass


def load_scenario(path: str | Path) -> dict[str, Any]:
    """读取一个场景 YAML 文件。

    Args:
        path: 场景 YAML 文件路径。

    Returns:
        解析后的场景数据。
    """
    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ScenarioError("scenario must be a YAML object")

    validate_scenario(data)
    return data


def validate_scenario(data: dict[str, Any]) -> None:
    """检查运行器需要的最少字段。

    Args:
        data: 解析后的场景数据。
    """
    required = ["id", "name", "environment", "faults", "agent_task", "solution_contract", "evaluation"]
    for key in required:
        if not data.get(key):
            raise ScenarioError(f"missing required field: {key}")

    environment = data["environment"]
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

    faults = data["faults"]
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

    agent_task = data["agent_task"]
    if not isinstance(agent_task, dict):
        raise ScenarioError("agent_task must be an object")
    if not isinstance(agent_task.get("instruction"), str) or not agent_task["instruction"].strip():
        raise ScenarioError("agent_task.instruction must be a non-empty string")

    solution_contract = data["solution_contract"]
    if not isinstance(solution_contract, dict):
        raise ScenarioError("solution_contract must be an object")
    allowed_actions = solution_contract.get("allowed_actions")
    if not isinstance(allowed_actions, list) or not allowed_actions:
        raise ScenarioError("solution_contract.allowed_actions must be a non-empty list")
    if not all(isinstance(action, str) and action for action in allowed_actions):
        raise ScenarioError("solution_contract.allowed_actions must only contain non-empty strings")

    evaluation = data["evaluation"]
    if not isinstance(evaluation, dict):
        raise ScenarioError("evaluation must be an object")
    if not isinstance(evaluation.get("type"), str) or not evaluation["type"].strip():
        raise ScenarioError("evaluation.type must be a non-empty string")
