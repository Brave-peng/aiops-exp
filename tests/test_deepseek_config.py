from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiops_bench.llm.deepseek import read_config_value
from aiops_bench.llm.deepseek import read_timeout_seconds


class DeepSeekConfigTests(unittest.TestCase):
    def test_reads_env_before_dotenv(self) -> None:
        with patch.dict(os.environ, {"DEEPSEEK_MODEL": "from-env"}):
            with patch("aiops_bench.llm.deepseek.find_dotenv", return_value=None):
                self.assertEqual(read_config_value("DEEPSEEK_MODEL"), "from-env")

    def test_reads_dotenv_when_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("DEEPSEEK_MODEL=from-dotenv\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                with patch("aiops_bench.llm.deepseek.find_dotenv", return_value=env_path):
                    self.assertEqual(read_config_value("DEEPSEEK_MODEL"), "from-dotenv")

    def test_reads_timeout_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("DEEPSEEK_TIMEOUT_SECONDS=3\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                with patch("aiops_bench.llm.deepseek.find_dotenv", return_value=env_path):
                    self.assertEqual(read_timeout_seconds(), 3)


if __name__ == "__main__":
    unittest.main()
