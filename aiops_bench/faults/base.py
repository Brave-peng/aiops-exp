from __future__ import annotations

from typing import Any
from typing import Protocol


class FaultInjector(Protocol):
    """故障注入器接口。"""

    type: str

    def inject(self, fault: dict[str, Any]) -> dict[str, Any]:
        """注入故障并返回 handle。"""
        ...

    def cleanup(self, handle: dict[str, Any]) -> dict[str, Any]:
        """基于 handle 清理故障。"""
        ...
