from __future__ import annotations

from pathlib import Path
from typing import Any

from aiops_bench.agents.deepseek import build_deepseek_proposal_prompt, solve_with_deepseek_agent
from aiops_bench.agents.manual import build_agent_prompt, pending_manual_proposal
from aiops_bench.environment.k8s import cleanup_environment, setup_environment
from aiops_bench.evaluators.deepseek import build_evaluation_prompt, evaluate_deepseek
from aiops_bench.evaluators.manual import evaluate_manual
from aiops_bench.faults.chaos_mesh import cleanup_faults, inject_faults
from aiops_bench.observability import collect_observations, render_observations_markdown
from aiops_bench.results.writer import build_run_artifact, create_run_dir, write_json, write_report, write_run_files
from aiops_bench.scenario import load_scenario


def run_scenario(
    scenario_path: str | Path,
    agent: str | None = None,
    proposer: str | None = None,
    judge: str | None = None,
    results_root: str | Path = "results",
    ai: bool = False,
) -> dict[str, Any]:
    """运行一个场景。"""
    scenario = load_scenario(scenario_path)
    proposer_name, judge_name = resolve_participants(
        scenario,
        agent=agent,
        proposer=proposer,
        judge=judge,
        ai=ai,
    )
    validate_participants(proposer_name, judge_name)
    run_dir = create_run_dir(scenario["id"], results_root)

    environment_result: dict[str, Any] | None = None
    fault_handles: list[dict[str, Any]] = []
    observations: dict[str, Any] = {"status": "not_collected", "commands": []}
    observations_markdown = "# Kubernetes 观测\n\n未采集观测。\n"
    fault_cleanup: list[dict[str, Any]] = []
    environment_cleanup: dict[str, Any] | None = None
    agent_prompt = ""
    evaluation_prompt = ""
    proposal: dict[str, Any] = {}
    evaluation: dict[str, Any] = {}
    summary: dict[str, Any] | None = None

    try:
        environment_result = setup_environment(scenario["environment"])
        fault_handles = inject_faults(scenario["faults"])
        observations = collect_observations(scenario, fault_handles)
        observations_markdown = render_observations_markdown(observations)
        agent_prompt = build_proposal_prompt(proposer_name, scenario, observations)
        inactive_faults = [fault for fault in fault_handles if fault.get("status") != "active"]
        if inactive_faults:
            proposal = {
                "status": "skipped",
                "message": "fault injection did not become active; benchmark run is invalid",
                "faults": inactive_faults,
            }
            evaluation = {
                "type": "skipped",
                "status": "skipped",
                "message": "fault injection did not become active; proposer and judge were skipped",
            }
            evaluation_prompt = build_evaluation_prompt(scenario, observations, proposal)
            summary = build_summary(
                scenario,
                run_dir,
                proposer_name,
                judge_name,
                environment_result,
                fault_handles,
                observations,
                proposal,
                evaluation,
                run_status="invalid",
            )
            write_run_files(
                run_dir,
                scenario,
                agent_prompt,
                evaluation_prompt,
                observations,
                observations_markdown,
                proposal,
                evaluation,
                summary,
            )
            return summary
        try:
            proposal = propose(proposer_name, scenario, observations)
        except Exception as exc:
            proposal = failed_result(exc)
            evaluation = {
                "type": "skipped",
                "status": "skipped",
                "message": "proposal phase failed",
            }
            evaluation_prompt = build_evaluation_prompt(scenario, observations, proposal)
            summary = build_summary(
                scenario,
                run_dir,
                proposer_name,
                judge_name,
                environment_result,
                fault_handles,
                observations,
                proposal,
                evaluation,
                exc,
            )
            write_run_files(
                run_dir,
                scenario,
                agent_prompt,
                evaluation_prompt,
                observations,
                observations_markdown,
                proposal,
                evaluation,
                summary,
            )
            return summary

        evaluation_prompt = build_evaluation_prompt(scenario, observations, proposal)
        try:
            evaluation = judge_proposal(judge_name, scenario, observations, proposal)
        except Exception as exc:
            evaluation = failed_result(exc, result_type=judge_name)
            summary = build_summary(
                scenario,
                run_dir,
                proposer_name,
                judge_name,
                environment_result,
                fault_handles,
                observations,
                proposal,
                evaluation,
                exc,
            )
            write_run_files(
                run_dir,
                scenario,
                agent_prompt,
                evaluation_prompt,
                observations,
                observations_markdown,
                proposal,
                evaluation,
                summary,
            )
            return summary

        summary = build_summary(
            scenario,
            run_dir,
            proposer_name,
            judge_name,
            environment_result,
            fault_handles,
            observations,
            proposal,
            evaluation,
        )
        write_run_files(
            run_dir,
            scenario,
            agent_prompt,
            evaluation_prompt,
            observations,
            observations_markdown,
            proposal,
            evaluation,
            summary,
        )
        return summary
    except Exception as exc:
        proposal = failed_result(exc)
        evaluation = {
            "type": "skipped",
            "status": "skipped",
            "message": "setup or fault injection failed",
        }
        summary = build_setup_failed_summary(
            scenario,
            run_dir,
            proposer_name,
            judge_name,
            environment_result,
            fault_handles,
            observations,
            exc,
        )
        write_run_failure(run_dir, scenario, proposer_name, observations, summary, exc)
        return summary
    finally:
        cleanup_errors: list[dict[str, str]] = []
        if fault_handles:
            try:
                fault_cleanup = cleanup_faults(fault_handles)
            except Exception as exc:  # pragma: no cover - defensive cleanup path
                cleanup_errors.append({"phase": "faults", "error": str(exc)})
        try:
            environment_cleanup = cleanup_environment(scenario["environment"])
        except Exception as exc:  # pragma: no cover - defensive cleanup path
            cleanup_errors.append({"phase": "environment", "error": str(exc)})
        if run_dir.exists():
            cleanup_summary = {
                "faults": fault_cleanup,
                "environment": environment_cleanup,
                "errors": cleanup_errors,
            }
            if summary is not None:
                summary["cleanup_status"] = "completed" if not cleanup_errors else "failed"
                summary["cleanup"] = cleanup_summary
                write_json(
                    run_dir / "run.json",
                    build_run_artifact(summary, agent_prompt, evaluation_prompt, proposal, evaluation),
                )
                write_report(
                    run_dir,
                    scenario,
                    summary,
                    proposal,
                    evaluation,
                    observations,
                    cleanup=cleanup_summary,
                    agent_prompt=agent_prompt,
                    observations_markdown=observations_markdown,
                )
            write_json(run_dir / "cleanup.json", cleanup_summary)


def validate_participants(proposer: str, judge: str) -> None:
    """校验 proposer/judge；mock 已停用，避免生成伪造通过结果。"""
    allowed = {"manual", "deepseek"}
    disabled = {"mock"}
    if proposer in disabled or judge in disabled:
        raise ValueError("mock proposer/judge 已停用，请使用 'manual' 或 'deepseek'")
    if proposer not in allowed:
        raise ValueError("proposer must be 'manual' or 'deepseek'")
    if judge not in allowed:
        raise ValueError("judge must be 'manual' or 'deepseek'")


def resolve_participants(
    scenario: dict[str, Any],
    *,
    agent: str | None,
    proposer: str | None,
    judge: str | None,
    ai: bool,
) -> tuple[str, str]:
    """解析 proposer/judge；--ai 同时启用两个 AI Agent。"""
    if ai:
        return proposer or "deepseek", judge or "deepseek"
    return proposer or agent or "manual", judge or scenario["evaluation"]["type"]


def build_proposal_prompt(
    proposer: str,
    scenario: dict[str, Any],
    observations: dict[str, Any],
) -> str:
    """构造 proposer prompt。"""
    if proposer == "deepseek":
        return build_deepseek_proposal_prompt(scenario, observations)
    if proposer == "manual":
        return build_agent_prompt(scenario)
    raise ValueError("proposer must be 'manual' or 'deepseek'")


def propose(
    proposer: str,
    scenario: dict[str, Any],
    observations: dict[str, Any],
) -> dict[str, Any]:
    """调用 proposer。"""
    if proposer == "manual":
        return pending_manual_proposal()
    if proposer == "deepseek":
        return solve_with_deepseek_agent(scenario, observations)
    raise ValueError("proposer must be 'manual' or 'deepseek'")


def judge_proposal(
    judge: str,
    scenario: dict[str, Any],
    observations: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """调用 judge。"""
    if judge == "manual":
        return evaluate_manual(scenario, proposal)
    if judge == "deepseek":
        return evaluate_deepseek(scenario, observations, proposal)
    raise ValueError("judge must be 'manual' or 'deepseek'")


def build_summary(
    scenario: dict[str, Any],
    run_dir: Path,
    proposer: str,
    judge: str,
    environment_result: dict[str, Any] | None,
    fault_handles: list[dict[str, Any]],
    observations: dict[str, Any],
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    exc: Exception | None = None,
    run_status: str = "completed",
) -> dict[str, Any]:
    """构造运行摘要。"""
    summary: dict[str, Any] = {
        "scenario_id": scenario["id"],
        "run_status": run_status,
        "proposer": proposer,
        "judge": judge,
        "run_dir": str(run_dir),
        "environment": environment_result,
        "faults": fault_handles,
        "observations_status": "collected" if observations.get("commands") else observations.get("status", "unknown"),
        "proposal_status": proposal.get("status", "ready"),
        "evaluation_status": evaluation["status"],
    }
    if exc is not None:
        summary["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return summary


def build_setup_failed_summary(
    scenario: dict[str, Any],
    run_dir: Path,
    proposer: str,
    judge: str,
    environment_result: dict[str, Any] | None,
    fault_handles: list[dict[str, Any]],
    observations: dict[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    """构造 setup/injection 阶段失败摘要，保证 run.json 仍可落盘。"""
    return {
        "scenario_id": scenario["id"],
        "run_status": "failed",
        "proposer": proposer,
        "judge": judge,
        "run_dir": str(run_dir),
        "environment": environment_result,
        "faults": fault_handles,
        "observations_status": "collected" if observations.get("commands") else observations.get("status", "unknown"),
        "proposal_status": "failed",
        "evaluation_status": "skipped",
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }


def failed_result(exc: Exception, result_type: str | None = None) -> dict[str, Any]:
    """构造阶段失败结果。"""
    result: dict[str, Any] = {
        "status": "failed",
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    if result_type is not None:
        result["type"] = result_type
    return result


def write_run_failure(
    run_dir: Path,
    scenario: dict[str, Any],
    proposer: str,
    observations: dict[str, Any],
    summary: dict[str, Any],
    exc: Exception,
) -> None:
    """写入失败状态文件。"""
    proposal = failed_result(exc)
    evaluation = {
        "type": "skipped",
        "status": "skipped",
        "message": "proposal phase failed",
    }
    try:
        agent_prompt = build_proposal_prompt(proposer, scenario, observations)
    except Exception:
        agent_prompt = build_agent_prompt(scenario)
    evaluation_prompt = build_evaluation_prompt(scenario, observations, proposal)
    observations_markdown = render_observations_markdown(observations)
    write_run_files(
        run_dir,
        scenario,
        agent_prompt,
        evaluation_prompt,
        observations,
        observations_markdown,
        proposal,
        evaluation,
        summary,
    )
