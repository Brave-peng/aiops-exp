from __future__ import annotations

from typing import Any
from typing import Protocol


class ObservationSource(Protocol):
    """观测数据源接口。"""

    type: str

    def collect(self, scenario: dict[str, Any], fault_handles: list[dict[str, Any]]) -> dict[str, Any]:
        """采集观测数据。"""
        ...
