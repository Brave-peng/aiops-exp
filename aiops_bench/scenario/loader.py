from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aiops_bench.scenario.schema import ScenarioContext, ScenarioError, validate_scenario


def load_scenario(path: str | Path) -> dict[str, Any]:
    """读取一个场景 YAML 文件。"""
    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ScenarioError("scenario must be a YAML object")

    validate_scenario(data)
    return data


def load_scenario_context(path: str | Path) -> ScenarioContext:
    """读取场景并附带路径解析上下文。"""
    scenario_path = Path(path).resolve()
    project_root = find_project_root(scenario_path.parent)
    data = load_scenario(scenario_path)
    return ScenarioContext(data=data, path=scenario_path, project_root=project_root)


def find_project_root(start: Path) -> Path:
    """从场景文件位置向上寻找项目根目录。"""
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "aiops_bench").is_dir():
            return candidate
    return start
