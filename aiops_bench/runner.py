from __future__ import annotations

from pathlib import Path
from typing import Any

from aiops_bench.agents.manual import build_agent_prompt, pending_manual_proposal
from aiops_bench.agents.mock import solve_with_mock_agent
from aiops_bench.environment.k8s import cleanup_environment, setup_environment
from aiops_bench.evaluators.manual import evaluate_manual
from aiops_bench.evaluators.mock import evaluate_mock
from aiops_bench.faults.chaos_mesh import cleanup_faults, inject_faults
from aiops_bench.results.writer import create_run_dir, write_json, write_run_files
from aiops_bench.scenario import load_scenario


def run_scenario(
    scenario_path: str | Path,
    agent: str = "manual",
    results_root: str | Path = "results",
) -> dict[str, Any]:
    """运行一个场景。"""
    scenario = load_scenario(scenario_path)
    run_dir = create_run_dir(scenario["id"], results_root)

    environment_result: dict[str, Any] | None = None
    fault_handles: list[dict[str, Any]] = []
    fault_cleanup: list[dict[str, Any]] = []
    environment_cleanup: dict[str, Any] | None = None

    try:
        environment_result = setup_environment(scenario["environment"])
        fault_handles = inject_faults(scenario["faults"])
        prompt = build_agent_prompt(scenario)

        if agent == "manual":
            proposal = pending_manual_proposal()
        elif agent == "mock":
            proposal = solve_with_mock_agent(scenario)
        else:
            raise ValueError("agent must be 'manual' or 'mock'")

        if scenario["evaluation"]["type"] == "mock":
            evaluation = evaluate_mock(scenario, proposal)
        else:
            evaluation = evaluate_manual(scenario, proposal)

        summary = {
            "scenario_id": scenario["id"],
            "agent": agent,
            "run_dir": str(run_dir),
            "environment": environment_result,
            "faults": fault_handles,
            "proposal_status": proposal.get("status", "ready"),
            "evaluation_status": evaluation["status"],
        }
        write_run_files(run_dir, scenario, prompt, proposal, evaluation, summary)
        return summary
    finally:
        if fault_handles:
            fault_cleanup = cleanup_faults(fault_handles)
        environment_cleanup = cleanup_environment(scenario["environment"])
        if run_dir.exists():
            cleanup_summary = {
                "faults": fault_cleanup,
                "environment": environment_cleanup,
            }
            write_json(run_dir / "cleanup.json", cleanup_summary)
