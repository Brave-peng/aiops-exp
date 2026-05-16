from __future__ import annotations

import unittest

from aiops_bench.runner import resolve_participants


class RunnerParticipantTests(unittest.TestCase):
    def test_defaults_to_ai_participants(self) -> None:
        proposer, judge = resolve_participants(
            proposer=None,
            judge=None,
            manual=False,
        )

        self.assertEqual(proposer, "deepseek")
        self.assertEqual(judge, "deepseek")

    def test_manual_flag_uses_manual_participants(self) -> None:
        proposer, judge = resolve_participants(
            proposer=None,
            judge=None,
            manual=True,
        )

        self.assertEqual(proposer, "manual")
        self.assertEqual(judge, "manual")

    def test_explicit_participants_override_defaults(self) -> None:
        proposer, judge = resolve_participants(
            proposer="manual",
            judge="deepseek",
            manual=False,
        )

        self.assertEqual(proposer, "manual")
        self.assertEqual(judge, "deepseek")


if __name__ == "__main__":
    unittest.main()
