from __future__ import annotations

import unittest
from pathlib import Path

from aiops_bench.scenario import ScenarioError
from aiops_bench.scenario import get_workload
from aiops_bench.scenario import load_scenario_context
from aiops_bench.scenario import validate_scenario


class ScenarioTests(unittest.TestCase):
    def test_workload_is_required(self) -> None:
        scenario = minimal_scenario()
        scenario.pop("workload")

        with self.assertRaisesRegex(ScenarioError, "missing required field: workload"):
            validate_scenario(scenario)

    def test_get_workload_returns_explicit_contract(self) -> None:
        workload = get_workload(minimal_scenario())

        self.assertEqual(workload["namespace"], "aiops-t1")
        self.assertEqual(workload["kind"], "Deployment")
        self.assertEqual(workload["selector"], {"app": "demo-service"})

    def test_context_resolves_paths_from_project_root(self) -> None:
        context = load_scenario_context(Path("scenarios/T1_cpu_saturation.yaml"))

        self.assertTrue((context.resolve_path("deploy/demo-app/k8s.yaml")).is_file())


def minimal_scenario() -> dict[str, object]:
    return {
        "id": "T1_cpu_saturation",
        "name": "demo-service CPU 饱和",
        "environment": {
            "type": "k8s",
            "namespace": "aiops-t1",
            "setup": [{"type": "kubectl_apply", "path": "deploy/demo-app/k8s.yaml"}],
            "readiness": [{"type": "kubectl_rollout", "resource": "deployment/demo-service"}],
            "cleanup": {"mode": "delete_namespace"},
        },
        "workload": {
            "namespace": "aiops-t1",
            "kind": "Deployment",
            "name": "demo-service",
            "selector": {"app": "demo-service"},
            "containers": ["demo-service"],
        },
        "faults": [
            {
                "id": "cpu_stress",
                "type": "chaos_mesh.stress_cpu",
                "target": {"namespace": "aiops-t1", "selector": {"app": "demo-service"}},
                "spec": {"workers": 2, "load": 100, "duration": "5m"},
            }
        ],
        "agent_task": {"instruction": "诊断问题并给出建议。"},
        "solution_contract": {"allowed_actions": ["kubectl_scale"]},
        "evaluation": {"type": "manual"},
    }


if __name__ == "__main__":
    unittest.main()
