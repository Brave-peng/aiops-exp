from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
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
    proposer: Annotated[Optional[str], typer.Option("--proposer", help="'manual' 或 'deepseek'")] = None,
    judge: Annotated[Optional[str], typer.Option("--judge", help="'manual' 或 'deepseek'；默认 deepseek")] = None,
    manual: Annotated[bool, typer.Option("--manual", help="使用人工 proposer 和人工 judge，不调用 AI")] = False,
    results_root: Annotated[Path, typer.Option("--results-root", help="结果输出目录")] = Path("results"),
) -> None:
    """运行单个场景，默认启用 AI 建议和 AI 评估。"""
    try:
        result = run_scenario(
            scenario,
            proposer=proposer,
            judge=judge,
            results_root=results_root,
            manual=manual,
        )
    except ValueError as exc:
        typer.echo(f"参数错误：{exc}", err=True)
        raise typer.Exit(code=2) from exc
    print_run_summary(result)


def print_json(data: Any) -> None:
    """按易读 JSON 格式打印数据。

    Args:
        data: 要打印的数据。
    """
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_run_summary(result: dict[str, Any]) -> None:
    """打印中文优先的运行摘要。"""
    evaluation_status = result.get("evaluation_status")
    run_status = result.get("run_status")
    if run_status == "completed" and evaluation_status == "passed":
        verdict = "通过"
    elif run_status == "completed" and evaluation_status == "pending":
        verdict = "已完成，等待人工评估"
    elif run_status == "invalid":
        verdict = "无效运行"
    elif run_status == "failed" or evaluation_status == "failed":
        verdict = "失败"
    else:
        verdict = str(run_status)

    environment = result.get("environment") or {}
    faults = result.get("faults") or []
    cleanup_status = format_status(result.get("cleanup_status", "unknown"))

    print(f"{verdict} {result.get('scenario_id', '')}")
    print(f"运行目录：{result.get('run_dir', '')}")
    print("")
    print(f"环境：{environment.get('status', 'unknown')}")
    print(f"故障：{summarize_faults(faults)}")
    print(f"观测：{result.get('observations_status', 'unknown')}")
    print(f"建议：{result.get('proposal_status', 'unknown')}")
    print(f"评估：{evaluation_status}")
    print(f"清理：{cleanup_status}")
    print("")
    print("报告：report.md")


def summarize_faults(faults: list[dict[str, Any]]) -> str:
    """汇总故障状态。"""
    if not faults:
        return "none"
    return ", ".join(f"{fault.get('id', '')}={fault.get('status', '')}" for fault in faults)


def format_status(status: Any) -> str:
    """把内部状态转换为 CLI 中文状态。"""
    mapping = {
        "completed": "completed",
        "delete_requested": "已请求删除",
        "failed": "failed",
        "partial": "partial",
        "unknown": "unknown",
    }
    return mapping.get(status, str(status))


def main() -> None:
    """启动 Typer CLI。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    app()


if __name__ == "__main__":
    main()
