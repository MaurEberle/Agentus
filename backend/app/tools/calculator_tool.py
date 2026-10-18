from __future__ import annotations

import ast
import math
import operator
from typing import Any

from app.tools.models import ExecuteResult

_MAX_EXPONENT = 20
_MAX_FACTORIAL = 20
_MAX_ROUND_DIGITS = 12

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


def _number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("const")
    return value


def _as_int(value: int | float) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("int")


def _call(name: str, args: list[int | float]) -> int | float:
    if name == "sqrt":
        if len(args) != 1 or args[0] < 0:
            raise ValueError("sqrt")
        return math.sqrt(args[0])
    if name == "cbrt":
        if len(args) != 1:
            raise ValueError("cbrt")
        return math.cbrt(args[0])
    if name == "abs":
        if len(args) != 1:
            raise ValueError("abs")
        return abs(args[0])
    if name == "round":
        if len(args) == 1:
            return round(args[0])
        if len(args) == 2:
            digits = _as_int(args[1])
            if abs(digits) > _MAX_ROUND_DIGITS:
                raise ValueError("round")
            return round(args[0], digits)
        raise ValueError("round")
    if name == "floor":
        if len(args) != 1:
            raise ValueError("floor")
        return math.floor(args[0])
    if name == "ceil":
        if len(args) != 1:
            raise ValueError("ceil")
        return math.ceil(args[0])
    if name in {"min", "max"}:
        if not args:
            raise ValueError(name)
        return min(args) if name == "min" else max(args)
    if name == "log":
        if len(args) == 1:
            return math.log(args[0])
        if len(args) == 2:
            return math.log(args[0], args[1])
        raise ValueError("log")
    if name == "ln":
        if len(args) != 1:
            raise ValueError("ln")
        return math.log(args[0])
    if name == "log10":
        if len(args) != 1:
            raise ValueError("log10")
        return math.log10(args[0])
    if name == "exp":
        if len(args) != 1:
            raise ValueError("exp")
        return math.exp(args[0])
    if name == "sin":
        if len(args) != 1:
            raise ValueError("sin")
        return math.sin(args[0])
    if name == "cos":
        if len(args) != 1:
            raise ValueError("cos")
        return math.cos(args[0])
    if name == "tan":
        if len(args) != 1:
            raise ValueError("tan")
        return math.tan(args[0])
    if name == "factorial":
        if len(args) != 1:
            raise ValueError("factorial")
        n = _as_int(args[0])
        if n < 0 or n > _MAX_FACTORIAL:
            raise ValueError("factorial")
        return math.factorial(n)
    raise ValueError("call")


def _eval(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError("pow")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return math.pi
        if node.id == "e":
            return math.e
        raise ValueError("name")
    if isinstance(node, ast.Call):
        if node.keywords or not isinstance(node.func, ast.Name):
            raise ValueError("call")
        return _call(node.func.id, [_eval(arg) for arg in node.args])
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
