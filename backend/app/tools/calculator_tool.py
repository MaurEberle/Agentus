from __future__ import annotations

import ast
import math
import operator
from typing import Any

from app.tools.models import ExecuteResult

_BIN_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _fail() -> ExecuteResult:
    return ExecuteResult(ok=False, error_key="tools.calculator.invalidExpression")


def _eval(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("const")
        return value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 8:
            raise ValueError("pow")
        return _BIN_OPS[type(node.op)](left, right)
    raise ValueError("node")


def _json_number(value: int | float) -> int | float:
    if isinstance(value, bool):
        raise ValueError("bool")
    if isinstance(value, int) and abs(value) < 1_000_000_000_000_000:
        return value
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("inf")
    return number


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    raw = "" if args is None else str(args.get("expression") or "")
    expression = raw.strip()
    if not expression or len(expression) > 200:
        return _fail()
    try:
        tree = ast.parse(expression, mode="eval")
        value = _json_number(_eval(tree))
    except (SyntaxError, ValueError, TypeError, OverflowError, ZeroDivisionError):
        return _fail()
    return ExecuteResult(ok=True, result={"value": value})
