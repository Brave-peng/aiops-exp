from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def setup_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """创建测试环境。"""
    namespace = environment["namespace"]
    ensure_kubernetes_context()
    ensure_namespace(namespace)

    setup_results = [run_setup_step(step, namespace) for step in environment["setup"]]
    readiness_results = [run_readiness_step(step, namespace) for step in environment["readiness"]]

    return {
        "type": environment["type"],
        "namespace": namespace,
        "status": "ready",
        "setup": setup_results,
        "readiness": readiness_results,
    }


def cleanup_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """清理测试环境。"""
    namespace = environment["namespace"]
    cleanup = environment.get("cleanup", {})
    mode = cleanup.get("mode")

    if mode != "delete_namespace":
        return {
            "type": environment["type"],
            "namespace": namespace,
            "status": "skipped",
            "message": f"unsupported cleanup mode: {mode}",
        }

    result = run_kubectl(
        ["delete", "namespace", namespace, "--ignore-not-found=true", "--wait=false"],
        check=False,
    )
    return {
        "type": environment["type"],
        "namespace": namespace,
        "status": "deleted" if result["returncode"] == 0 else "failed",
        "command": result["command"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def ensure_kubernetes_context() -> None:
    """确认 kubectl 当前有可用 context。"""
    run_kubectl(["config", "current-context"])


def ensure_namespace(namespace: str) -> None:
    """创建 namespace；已存在时直接复用。"""
    result = run_kubectl(["get", "namespace", namespace], check=False)
    if result["returncode"] == 0:
        return
    run_kubectl(["create", "namespace", namespace])


def run_setup_step(step: dict[str, Any], namespace: str) -> dict[str, Any]:
    """执行一个环境 setup 步骤。"""
    step_type = step.get("type")
    if step_type != "kubectl_apply":
        raise ValueError(f"unsupported environment setup step: {step_type}")

    manifest_path = Path(step["path"])
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    result = run_kubectl(["apply", "-n", namespace, "-f", str(manifest_path)])
    return {
        "type": step_type,
        "path": str(manifest_path),
        "status": "applied",
        "command": result["command"],
        "stdout": result["stdout"],
    }


def run_readiness_step(step: dict[str, Any], namespace: str) -> dict[str, Any]:
    """执行一个 readiness 检查步骤。"""
    step_type = step.get("type")
    if step_type != "kubectl_rollout":
        raise ValueError(f"unsupported environment readiness step: {step_type}")

    rollout_namespace = step.get("namespace", namespace)
    timeout = int(step.get("timeout_seconds", 120))
    result = run_kubectl(
        [
            "rollout",
            "status",
            step["resource"],
            "-n",
            rollout_namespace,
            f"--timeout={timeout}s",
        ]
    )
    return {
        "type": step_type,
        "resource": step["resource"],
        "namespace": rollout_namespace,
        "status": "ready",
        "command": result["command"],
        "stdout": result["stdout"],
    }


def run_kubectl(args: list[str], check: bool = True, input_text: str | None = None) -> dict[str, Any]:
    """执行固定模板生成的 kubectl 命令。"""
    command = ["kubectl", *args]
    try:
        completed = subprocess.run(
            command,
            check=False,
            input=input_text,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        result = {
            "command": command,
            "returncode": 127,
            "stdout": "",
            "stderr": "kubectl executable not found",
        }
        if check:
            raise RuntimeError(result["stderr"]) from exc
        return result

    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if check and completed.returncode != 0:
        raise RuntimeError(
            "kubectl command failed: "
            + " ".join(command)
            + f"\nstdout: {result['stdout']}\nstderr: {result['stderr']}"
        )
    return result
