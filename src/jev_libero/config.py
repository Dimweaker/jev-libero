"""Declarative task contracts. No eval, imports, or executable Python in JSON."""

import copy
import json
import operator
from pathlib import Path

import numpy as np

TASKS = Path(__file__).with_name("tasks")
DEFAULT = TASKS / "microwave.json"


def task_path(value=None):
    """Resolve a bundled task name or an explicit JSON path."""
    if value is None:
        return DEFAULT
    candidate = TASKS / f"{value}.json"
    return candidate if candidate.is_file() else Path(value)


BINARY = {
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    "div": operator.truediv,
    "ge": operator.ge,
    "gt": operator.gt,
    "le": operator.le,
    "lt": operator.lt,
    "eq": operator.eq,
}
OPS = set(BINARY) | {"ref", "all", "any", "not", "norm", "round", "index"}


def expression(node, context):
    if isinstance(node, list):
        return [expression(x, context) for x in node]
    if not isinstance(node, dict):
        return node
    if len(node) != 1:
        raise ValueError(f"Expression must have one operator: {node}")
    op, args = next(iter(node.items()))
    if op == "ref":
        value = context
        for key in args.split("."):
            value = value[key]
        return value
    if op == "all":
        return all(expression(x, context) for x in args)
    if op == "any":
        return any(expression(x, context) for x in args)
    if op == "not":
        return not expression(args, context)
    if op == "norm":
        return float(np.linalg.norm(expression(args, context)))
    values = expression(args, context)
    if op in BINARY:
        if op in ("add", "sub", "mul", "div") and any(isinstance(v, list) for v in values):
            return np.asarray(BINARY[op](*(np.asarray(v) for v in values))).tolist()
        return BINARY[op](*values)
    if op == "round":
        return round(*values)
    if op == "index":
        return values[0][values[1]]
    raise ValueError(f"Unsupported expression operator: {op}")


def project(spec, context):
    return {key: expression(value, context) for key, value in spec.items()}


def validate_expression(node):
    if isinstance(node, list):
        for value in node:
            validate_expression(value)
    elif isinstance(node, dict):
        if len(node) != 1 or next(iter(node)) not in OPS:
            raise ValueError(f"Unsupported expression: {node}")
        op, value = next(iter(node.items()))
        if op != "ref":
            validate_expression(value)


def load_task(path=None):
    if isinstance(path, dict):
        cfg = copy.deepcopy(path)
    else:
        cfg = json.loads(task_path(path).read_text(encoding="utf-8"))
    if cfg["schema_version"] != 1:
        raise ValueError("Unsupported task configuration version")
    for key in (
        "binding",
        "contact",
        "features",
        "predictions",
        "thresholds",
        "contracts",
        "policy",
        "search",
        "display",
    ):
        if key not in cfg:
            raise ValueError(f"Missing task configuration section: {key}")
    expressions = [
        *cfg["features"].values(),
        *cfg["predictions"].values(),
        *cfg["contracts"].values(),
        *cfg["search"]["score"],
    ]
    for group in ("feedback", "intent_state", "strategy_state", "motor_options"):
        expressions.extend(cfg["policy"][group].values())
    for expr in expressions:
        validate_expression(expr)
    if set(cfg["contracts"]) != set(cfg["policy"]["intent_descriptions"]):
        raise ValueError("Contract/intent names differ")
    return cfg
