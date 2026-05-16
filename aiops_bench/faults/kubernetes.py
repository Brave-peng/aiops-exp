from __future__ import annotations

from typing import Any

from aiops_bench.environment.k8s import run_kubectl


class KubernetesSetEnvInjector:
    """通过修改 Deployment env 注入应用态故障。"""

    type = "k8s.set_env"

    def inject(self, fault: dict[str, Any]) -> dict[str, Any]:
        """通过修改 deployment env 注入代码级异常。"""
        target = fault["target"]
        spec = fault["spec"]
        namespace = target["namespace"]
        deployment = target["deployment"]
        env = spec["env"]
        env_args = [f"{key}={value}" for key, value in env.items()]
        result = run_kubectl(["set", "env", f"deployment/{deployment}", *env_args, "-n", namespace])
        rollout = run_kubectl(
            [
                "rollout",
                "status",
                f"deployment/{deployment}",
                "-n",
                namespace,
                f"--timeout={int(spec.get('timeout_seconds', 120))}s",
            ],
            check=False,
        )
        status = "active" if result["returncode"] == 0 and rollout["returncode"] == 0 else "failed"
        return {
            "id": fault["id"],
            "type": fault["type"],
            "name": deployment,
            "namespace": namespace,
            "resource": "deployment",
            "status": status,
            "command": result["command"],
            "stdout": result["stdout"],
            "verification": {
                "status": status,
                "status_reason": "deployment environment updated and rollout completed"
                if status == "active"
                else "deployment environment update or rollout failed",
                "rollout": rollout,
            },
            "env": env,
        }

    def cleanup(self, handle: dict[str, Any]) -> dict[str, Any]:
        """回滚 k8s.set_env 注入；namespace 删除仍会兜底。"""
        env = handle.get("env") or {}
        unset_args = [f"{key}-" for key in env]
        if not unset_args:
            return {
                "id": handle["id"],
                "type": handle["type"],
                "name": handle["name"],
                "namespace": handle["namespace"],
                "status": "skipped",
                "message": "no env keys to unset",
            }
        result = run_kubectl(
            ["set", "env", f"deployment/{handle['name']}", *unset_args, "-n", handle["namespace"]],
            check=False,
        )
        return {
            "id": handle["id"],
            "type": handle["type"],
            "name": handle["name"],
            "namespace": handle["namespace"],
            "status": "deleted" if result["returncode"] == 0 else "failed",
            "command": result["command"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
