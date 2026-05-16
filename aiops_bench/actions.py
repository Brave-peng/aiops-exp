from __future__ import annotations

from typing import Any


ACTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "kubectl_scale": {
        "required": ["namespace", "deployment", "replicas"],
        "description": "namespace、deployment、replicas",
    },
    "kubectl_set_resources": {
        "required": ["namespace", "deployment", "container"],
        "one_of": ["requests", "limits"],
        "description": "namespace、deployment、container，以及 requests 或 limits 至少一个",
    },
    "kubectl_restart": {
        "required": ["namespace", "deployment"],
        "description": "namespace、deployment",
    },
    "kubectl_set_env": {
        "required": ["namespace", "deployment", "env"],
        "description": "namespace、deployment、env 字典",
    },
}


def render_action_contract(allowed_actions: list[str]) -> str:
    """渲染允许动作的参数契约，供 prompt 和文档复用。"""
    lines = []
    for action_type in allowed_actions:
        contract = ACTION_CONTRACTS.get(action_type)
        if contract is None:
            lines.append(f"- {action_type}.params：未定义参数契约")
        else:
            lines.append(f"- {action_type}.params：{contract['description']}")
    return "\n".join(lines)


def validate_proposal_actions(scenario: dict[str, Any], proposal: dict[str, Any]) -> None:
    """校验 proposal actions 的白名单和参数契约。"""
    actions = proposal.get("proposed_actions")
    if not isinstance(actions, list):
        raise ValueError("proposal.proposed_actions must be a list")

    allowed = set(scenario["solution_contract"]["allowed_actions"])
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"proposal.proposed_actions[{index}] must be an object")
        action_type = action.get("type")
        if action_type not in allowed:
            raise ValueError(f"unsupported proposed action type: {action_type}")
        if not isinstance(action.get("params"), dict):
            raise ValueError(f"proposal.proposed_actions[{index}].params must be an object")
        normalize_action(action)
        validate_action_params(index, action)
        if not isinstance(action.get("reason"), str) or not action["reason"].strip():
            raise ValueError(f"proposal.proposed_actions[{index}].reason must be a non-empty string")


def normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    """兼容常见 Kubernetes 资源写法，落到统一参数名。"""
    params = action.get("params", {})
    resource = params.get("resource") or params.get("name")
    if isinstance(resource, str) and resource.startswith("deployment/") and "deployment" not in params:
        params["deployment"] = resource.split("/", 1)[1]
    if action.get("type") == "kubectl_set_env" and isinstance(params.get("env"), dict):
        params["env"] = {key: "" if value is None else value for key, value in params["env"].items()}
    return action


def validate_action_params(index: int, action: dict[str, Any]) -> None:
    """校验支持动作的最小参数契约。"""
    action_type = action.get("type")
    params = action.get("params", {})
    contract = ACTION_CONTRACTS.get(str(action_type))
    if contract is None:
        return

    for name in contract.get("required", []):
        if name == "replicas":
            require_non_negative_int_param(index, params, name)
        elif name == "env":
            require_string_dict_param(index, params, name)
        else:
            require_string_param(index, params, name)

    one_of = contract.get("one_of")
    if one_of and not any(isinstance(params.get(name), dict) for name in one_of):
        names = " or ".join(one_of)
        raise ValueError(f"proposal.proposed_actions[{index}].params must include {names} object")


def require_string_param(index: int, params: dict[str, Any], name: str) -> None:
    """校验字符串参数。"""
    if not isinstance(params.get(name), str) or not params[name].strip():
        raise ValueError(f"proposal.proposed_actions[{index}].params.{name} must be a non-empty string")


def require_non_negative_int_param(index: int, params: dict[str, Any], name: str) -> None:
    """校验非负整数参数。"""
    if not isinstance(params.get(name), int) or params[name] < 0:
        raise ValueError(f"proposal.proposed_actions[{index}].params.{name} must be a non-negative integer")


def require_string_dict_param(index: int, params: dict[str, Any], name: str) -> None:
    """校验字符串字典参数。"""
    value = params.get(name)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"proposal.proposed_actions[{index}].params.{name} must be a non-empty object")
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(item, str):
            raise ValueError(
                f"proposal.proposed_actions[{index}].params.{name} must only contain string keys and values"
            )
