from __future__ import annotations

import unittest
from unittest.mock import patch

from aiops_bench.environment.k8s import cleanup_environment
from aiops_bench.runner import summarize_cleanup_status


class CleanupTest(unittest.TestCase):
    def test_cleanup_waits_for_namespace_deletion(self) -> None:
        environment = {
            "type": "k8s",
            "namespace": "aiops-t1",
            "cleanup": {"mode": "delete_namespace"},
        }
        results = [
            {
                "command": ["kubectl", "delete", "namespace", "aiops-t1"],
                "returncode": 0,
                "stdout": "namespace deleted",
                "stderr": "",
            },
            {
                "command": ["kubectl", "wait", "--for=delete", "namespace/aiops-t1"],
                "returncode": 0,
                "stdout": "namespace/aiops-t1 condition met",
                "stderr": "",
            },
        ]

        with patch("aiops_bench.environment.k8s.run_kubectl", side_effect=results) as run_kubectl:
            cleanup = cleanup_environment(environment)

        self.assertEqual(cleanup["status"], "deleted")
        self.assertEqual(cleanup["wait"]["returncode"], 0)
        self.assertEqual(run_kubectl.call_count, 2)

    def test_cleanup_reports_delete_requested_when_wait_times_out(self) -> None:
        environment = {
            "type": "k8s",
            "namespace": "aiops-t1",
            "cleanup": {"mode": "delete_namespace"},
        }
        results = [
            {
                "command": ["kubectl", "delete", "namespace", "aiops-t1"],
                "returncode": 0,
                "stdout": "namespace deleted",
                "stderr": "",
            },
            {
                "command": ["kubectl", "wait", "--for=delete", "namespace/aiops-t1"],
                "returncode": 1,
                "stdout": "",
                "stderr": "timed out waiting for the condition",
            },
        ]

        with patch("aiops_bench.environment.k8s.run_kubectl", side_effect=results):
            cleanup = cleanup_environment(environment)

        self.assertEqual(cleanup["status"], "delete_requested")

    def test_summary_does_not_mark_pending_delete_completed(self) -> None:
        status = summarize_cleanup_status(
            {
                "faults": [{"status": "deleted"}],
                "environment": {"status": "delete_requested"},
                "errors": [],
            }
        )

        self.assertEqual(status, "delete_requested")


if __name__ == "__main__":
    unittest.main()
