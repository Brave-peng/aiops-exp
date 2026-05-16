from __future__ import annotations

import unittest

from aiops_bench.faults.chaos_mesh import build_network_delay_manifest
from aiops_bench.faults.chaos_mesh import build_network_loss_manifest
from aiops_bench.faults.chaos_mesh import build_pod_kill_manifest
from aiops_bench.faults.chaos_mesh import build_stress_memory_manifest
from aiops_bench.faults.chaos_mesh import parse_networkchaos_verification
from aiops_bench.faults.chaos_mesh import parse_podchaos_verification


class FaultManifestTests(unittest.TestCase):
    def test_build_stress_memory_manifest(self) -> None:
        manifest = build_stress_memory_manifest(
            "aiops-memory-pressure",
            {
                "target": {
                    "namespace": "aiops-t2",
                    "selector": {"app": "demo-service"},
                },
                "spec": {"workers": 1, "size": "96MB", "duration": "5m"},
            },
        )

        self.assertEqual(manifest["kind"], "StressChaos")
        self.assertEqual(manifest["spec"]["selector"]["namespaces"], ["aiops-t2"])
        self.assertEqual(manifest["spec"]["stressors"]["memory"]["size"], "96MB")

    def test_build_network_delay_manifest(self) -> None:
        manifest = build_network_delay_manifest(
            "aiops-network-delay",
            {
                "target": {
                    "namespace": "aiops-t3",
                    "selector": {"app": "demo-service"},
                },
                "spec": {
                    "mode": "one",
                    "latency": "500ms",
                    "jitter": "50ms",
                    "correlation": "25",
                    "duration": "5m",
                },
            },
        )

        self.assertEqual(manifest["kind"], "NetworkChaos")
        self.assertEqual(manifest["spec"]["action"], "delay")
        self.assertEqual(manifest["spec"]["delay"]["latency"], "500ms")
        self.assertEqual(manifest["spec"]["selector"]["labelSelectors"], {"app": "demo-service"})

    def test_build_network_loss_manifest(self) -> None:
        manifest = build_network_loss_manifest(
            "aiops-network-loss",
            {
                "target": {
                    "namespace": "aiops-t4",
                    "selector": {"app": "demo-service"},
                },
                "spec": {
                    "mode": "one",
                    "loss": "35",
                    "correlation": "25",
                    "duration": "5m",
                },
            },
        )

        self.assertEqual(manifest["kind"], "NetworkChaos")
        self.assertEqual(manifest["spec"]["action"], "loss")
        self.assertEqual(manifest["spec"]["loss"]["loss"], "35")

    def test_build_pod_kill_manifest(self) -> None:
        manifest = build_pod_kill_manifest(
            "aiops-pod-kill",
            {
                "target": {
                    "namespace": "aiops-t5",
                    "selector": {"app": "demo-service"},
                },
                "spec": {"mode": "one"},
            },
        )

        self.assertEqual(manifest["kind"], "PodChaos")
        self.assertEqual(manifest["spec"]["action"], "pod-kill")
        self.assertEqual(manifest["spec"]["selector"]["namespaces"], ["aiops-t5"])

    def test_parse_networkchaos_verification_does_not_treat_existence_as_active(self) -> None:
        verification = parse_networkchaos_verification(
            {
                "returncode": 0,
                "stdout": "apiVersion: chaos-mesh.org/v1alpha1\nkind: NetworkChaos\nstatus: {}\n",
                "stderr": "",
                "command": ["kubectl", "get", "networkchaos"],
            }
        )

        self.assertEqual(verification["status"], "created")
        self.assertEqual(verification["failure_reason"], "")

    def test_parse_podchaos_verification_does_not_treat_existence_as_active(self) -> None:
        verification = parse_podchaos_verification(
            {
                "returncode": 0,
                "stdout": "apiVersion: chaos-mesh.org/v1alpha1\nkind: PodChaos\nstatus: {}\n",
                "stderr": "",
                "command": ["kubectl", "get", "podchaos"],
            }
        )

        self.assertEqual(verification["status"], "created")
        self.assertEqual(verification["failure_reason"], "")

    def test_parse_networkchaos_verification_uses_all_injected_as_active(self) -> None:
        verification = parse_networkchaos_verification(
            {
                "returncode": 0,
                "stdout": "\n".join(
                    [
                        "apiVersion: chaos-mesh.org/v1alpha1",
                        "kind: NetworkChaos",
                        "status:",
                        "  conditions:",
                        "    - type: AllInjected",
                        "      status: 'True'",
                    ]
                ),
                "stderr": "",
                "command": ["kubectl", "get", "networkchaos"],
            }
        )

        self.assertEqual(verification["status"], "active")


if __name__ == "__main__":
    unittest.main()
