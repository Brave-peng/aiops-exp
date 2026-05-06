from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated
from typing import Any

import typer

from aiops_bench.runner import run_scenario
from aiops_bench.scenario import load_scenario

app = typer.Typer(help="轻量级 AIOps 实验运行器")
logger = logging.getLogger(__name__)


@app.command("load")
def load_command(
    scenario: Annotated[Path, typer.Option("--scenario", "-s", help="场景 YAML 路径")],
) -> None:
    """读取并检查场景 YAML。"""
    data = load_scenario(scenario)
    print_json(data)


@app.command("run")
def run_command(
    scenario: Annotated[Path, typer.Option("--scenario", "-s", help="场景 YAML 路径")],
    agent: Annotated[str, typer.Option("--agent", "-a", help="'manual' 或 'mock'")] = "manual",
    results_root: Annotated[Path, typer.Option("--results-root", help="结果输出目录")] = Path("results"),
) -> None:
    """用一个 Agent 运行单个场景。"""
    result = run_scenario(scenario, agent=agent, results_root=results_root)
    print_json(result)


def print_json(data: Any) -> None:
    """按易读 JSON 格式打印数据。

    Args:
        data: 要打印的数据。
    """
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    """启动 Typer CLI。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    app()


if __name__ == "__main__":
    main()
