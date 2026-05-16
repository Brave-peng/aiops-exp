from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class DemoHandler(BaseHTTPRequestHandler):
    """演示服务的 HTTP 处理器。"""

    server_version = "demo-app/0.1"

    def do_GET(self) -> None:
        """处理所有 GET 路由。"""
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.write_json(HTTPStatus.OK, base_response("ok"))
            return
        if parsed.path == "/healthz":
            self.write_json(HTTPStatus.OK, base_response("healthy"))
            return
        if parsed.path == "/readyz":
            maybe_emit_code_fault()
            maybe_emit_config_fault()
            self.write_json(HTTPStatus.OK, base_response("ready"))
            return
        if parsed.path == "/config":
            response = base_response("config")
            response["env"] = {
                "SERVICE_NAME": getenv("SERVICE_NAME", "demo-service"),
                "DOWNSTREAM_URL": getenv("DOWNSTREAM_URL", ""),
                "PORT": getenv("PORT", "8080"),
                "BUG_MODE": getenv("BUG_MODE", ""),
            }
            self.write_json(HTTPStatus.OK, response)
            return
        if parsed.path == "/bug":
            maybe_emit_code_fault(force=True)
            self.write_json(HTTPStatus.INTERNAL_SERVER_ERROR, base_response("code exception"))
            return
        if parsed.path == "/work":
            query = parse_qs(parsed.query)
            duration_ms = int_query(query, "ms", 100)
            do_cpu_work(duration_ms)
            response = base_response("work complete")
            response["env"] = {"duration_ms": str(duration_ms)}
            self.write_json(HTTPStatus.OK, response)
            return

        self.write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        """通过 logging 模块输出请求日志。"""
        logger.info("%s - %s", self.address_string(), fmt % args)

    def write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        """写入 JSON 响应。

        Args:
            status: HTTP 状态码。
            payload: 响应内容。
        """
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def base_response(message: str) -> dict[str, Any]:
    """构造通用 JSON 响应内容。

    Args:
        message: 响应消息。

    Returns:
        响应内容。
    """
    return {
        "service": getenv("SERVICE_NAME", "demo-service"),
        "hostname": os.uname().nodename,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
    }


def getenv(key: str, fallback: str) -> str:
    """读取环境变量，空值时使用默认值。

    Args:
        key: 环境变量名。
        fallback: 环境变量为空时使用的默认值。

    Returns:
        环境变量值或默认值。
    """
    return os.environ.get(key) or fallback


def int_query(query: dict[str, list[str]], key: str, fallback: int) -> int:
    """读取整数类型的查询参数。

    Args:
        query: 解析后的查询参数。
        key: 查询参数名。
        fallback: 参数缺失或非法时使用的默认值。

    Returns:
        整数参数值。
    """
    raw_values = query.get(key)
    if not raw_values:
        return fallback

    try:
        value = int(raw_values[0])
    except ValueError:
        return fallback

    if value < 0:
        return fallback
    return min(value, 30_000)


def maybe_emit_code_fault(force: bool = False) -> None:
    """在代码异常场景下输出稳定的根因信号。"""
    if getenv("BUG_MODE", "") != "bad_parameter" and not force:
        return
    try:
        parse_positive_int("not-a-number")
    except ValueError:
        logger.exception(
            "code_fault=bad_parameter root_cause_indicator=stack_trace "
            "message='incorrect parameter values in demo-service'"
        )


def maybe_emit_config_fault() -> None:
    """在错误下游配置场景下输出稳定的配置异常信号。"""
    downstream_url = getenv("DOWNSTREAM_URL", "")
    if not downstream_url or "missing-dependency" not in downstream_url:
        return
    logger.error(
        "config_fault=bad_downstream_url root_cause_indicator=misconfiguration "
        "downstream_url=%s message='configured downstream service is unreachable'",
        downstream_url,
    )


def parse_positive_int(raw: str) -> int:
    """解析正整数；用于演示代码级参数错误。"""
    value = int(raw)
    if value <= 0:
        raise ValueError("value must be positive")
    return value


def do_cpu_work(duration_ms: int) -> None:
    """运行一小段 CPU 计算。

    Args:
        duration_ms: 计算时长，单位毫秒。
    """
    deadline = time.monotonic() + duration_ms / 1000
    value = 0.0001
    while time.monotonic() < deadline:
        value += math.sqrt(value)


def main() -> None:
    """启动演示 HTTP 服务。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    port = int(getenv("PORT", "8080"))
    service_name = getenv("SERVICE_NAME", "demo-service")
    server = ThreadingHTTPServer(("0.0.0.0", port), DemoHandler)
    logger.info("starting %s on :%s", service_name, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
