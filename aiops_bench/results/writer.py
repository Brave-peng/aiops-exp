from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def create_run_dir(scenario_id: str, results_root: str | Path = "results") -> Path:
    """创建本次实验的结果目录。"""
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(results_root) / scenario_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_run_files(
    run_dir: Path,
    scenario: dict[str, Any],
    agent_prompt: str,
    evaluation_prompt: str,
    observations: dict[str, Any],
    observations_markdown: str,
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    """写入本次实验的结果文件。"""
    write_yaml(run_dir / "scenario.yaml", scenario)
    (run_dir / "agent_prompt.md").write_text(agent_prompt, encoding="utf-8")
    (run_dir / "evaluation_prompt.md").write_text(evaluation_prompt, encoding="utf-8")
    write_json(run_dir / "observations.json", observations)
    (run_dir / "observations.md").write_text(observations_markdown, encoding="utf-8")
    write_json(run_dir / "proposal.json", proposal)
    write_json(run_dir / "evaluation.json", evaluation)
    write_json(run_dir / "run.json", summary)


def write_json(path: Path, data: Any) -> None:
    """写入易读 JSON。"""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: Any) -> None:
    """写入 YAML。"""
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
