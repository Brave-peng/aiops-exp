from __future__ import annotations

import unittest
from typing import Any

from aiops_bench.faults.manager import cleanup_faults
from aiops_bench.faults.manager import inject_faults


class RecordingInjector:
    type = "test.fault"

    def __init__(self) -> None:
        self.cleaned: list[dict[str, Any]] = []

    def inject(self, fault: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": fault["id"],
            "type": fault["type"],
            "name": "recorded",
            "namespace": "test",
            "status": "active",
        }

    def cleanup(self, handle: dict[str, Any]) -> dict[str, Any]:
        self.cleaned.append(handle)
        return {
            "id": handle["id"],
            "type": handle["type"],
            "name": handle["name"],
            "namespace": handle["namespace"],
            "status": "deleted",
        }


class FaultManagerTests(unittest.TestCase):
    def test_inject_faults_uses_registered_injector(self) -> None:
        injector = RecordingInjector()
        handles = inject_faults(
            [{"id": "one", "type": "test.fault", "target": {}, "spec": {}}],
            registry={injector.type: injector},
        )

        self.assertEqual(handles[0]["status"], "active")
        self.assertEqual(handles[0]["type"], "test.fault")

    def test_cleanup_faults_uses_registered_injector(self) -> None:
        injector = RecordingInjector()
        cleanup = cleanup_faults(
            [{"id": "one", "type": "test.fault", "name": "recorded", "namespace": "test"}],
            registry={injector.type: injector},
        )

        self.assertEqual(cleanup[0]["status"], "deleted")
        self.assertEqual(injector.cleaned[0]["id"], "one")

    def test_unsupported_fault_type_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fault type"):
            inject_faults(
                [{"id": "one", "type": "missing.fault", "target": {}, "spec": {}}],
                registry={},
            )


if __name__ == "__main__":
    unittest.main()
