from __future__ import annotations

import unittest

from aiops_bench.actions import render_action_contract, validate_proposal_actions


class ActionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = {
            "solution_contract": {
                "allowed_actions": [
                    "kubectl_scale",
                    "kubectl_set_resources",
                    "kubectl_restart",
                ],
            },
        }

    def test_render_action_contract_for_allowed_actions(self) -> None:
        rendered = render_action_contract(["kubectl_scale", "kubectl_restart"])

        self.assertIn("kubectl_scale.params", rendered)
        self.assertIn("namespace、deployment、replicas", rendered)
        self.assertIn("kubectl_restart.params", rendered)

    def test_validate_scale_action(self) -> None:
        proposal = {
            "proposed_actions": [
                {
                    "type": "kubectl_scale",
                    "params": {
                        "namespace": "aiops-t1",
                        "deployment": "demo-service",
                        "replicas": 2,
                    },
                    "reason": "缓解 CPU 压力。",
                }
            ],
        }

        validate_proposal_actions(self.scenario, proposal)

    def test_normalizes_deployment_resource_name(self) -> None:
        proposal = {
            "proposed_actions": [
                {
                    "type": "kubectl_restart",
                    "params": {
                        "namespace": "aiops-t1",
                        "resource": "deployment/demo-service",
                    },
                    "reason": "重启工作负载。",
                }
            ],
        }

        validate_proposal_actions(self.scenario, proposal)

        self.assertEqual(proposal["proposed_actions"][0]["params"]["deployment"], "demo-service")

    def test_rejects_invalid_resource_contract(self) -> None:
        proposal = {
            "proposed_actions": [
                {
                    "type": "kubectl_set_resources",
                    "params": {
                        "namespace": "aiops-t1",
                        "deployment": "demo-service",
                        "container": "demo-service",
                    },
                    "reason": "调整资源。",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "requests or limits"):
            validate_proposal_actions(self.scenario, proposal)


if __name__ == "__main__":
    unittest.main()
