from __future__ import annotations

import unittest

from aiops_bench.observability import build_kubernetes_commands
from aiops_bench.observability import build_kubernetes_evidence_items
from aiops_bench.observability import build_observation_sources


class ObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workload = {
            "namespace": "aiops-t3",
            "kind": "Deployment",
            "name": "demo-service",
            "selector": {"app": "demo-service"},
            "containers": ["demo-service"],
        }

    def test_build_kubernetes_commands_includes_fault_resources(self) -> None:
        commands = build_kubernetes_commands(
            "aiops-t3",
            [
                {
                    "type": "chaos_mesh.network_delay",
                    "resource": "networkchaos",
                    "name": "aiops-network-delay",
                    "namespace": "chaos-mesh",
                }
            ],
            self.workload,
        )

        self.assertIn(["describe", "deployment/demo-service", "-n", "aiops-t3"], commands)
        self.assertIn(
            ["logs", "-l", "app=demo-service", "-n", "aiops-t3", "--all-containers=true", "--tail=100"],
            commands,
        )
        self.assertIn(
            ["get", "networkchaos", "aiops-network-delay", "-n", "chaos-mesh", "-o", "yaml"],
            commands,
        )

    def test_build_kubernetes_evidence_items_normalizes_fault_and_commands(self) -> None:
        evidence = build_kubernetes_evidence_items(
            "aiops-t1",
            [
                {
                    "id": "cpu_stress",
                    "type": "chaos_mesh.stress_cpu",
                    "name": "aiops-cpu-stress",
                    "namespace": "chaos-mesh",
                    "status": "active",
                    "command": ["kubectl", "apply", "-f", "-"],
                    "verification": {"status_reason": "Chaos Mesh condition AllInjected=True"},
                }
            ],
            [
                {
                    "command": ["kubectl", "get", "po"],
                    "returncode": 0,
                    "stdout": "NAME READY\npod-a 1/1\n",
                    "stderr": "",
                }
            ],
        )

        self.assertEqual(evidence[0]["signal_type"], "fault")
        self.assertEqual(evidence[0]["confidence"], 0.9)
        self.assertEqual(evidence[1]["signal_type"], "command")

    def test_build_observation_sources_rejects_unknown_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported observation source type"):
            build_observation_sources({"observability": {"sources": [{"type": "prometheus"}]}})


if __name__ == "__main__":
    unittest.main()
