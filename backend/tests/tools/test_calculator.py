from __future__ import annotations

import math

from app.tools.execute import execute_first_party


def test_precedence() -> None:
    result = execute_first_party("calculator", args={"expression": "2+3*4"})
    assert result.ok is True
    assert result.result == {"value": 14}


def test_import_rejected() -> None:
    result = execute_first_party("calculator", args={"expression": '__import__("os")'})
    assert result.ok is False
    assert result.error_key == "tools.calculator.invalidExpression"


def test_pow_exponent_too_large() -> None:
    result = execute_first_party("calculator", args={"expression": "2**21"})
    assert result.ok is False
    assert result.error_key == "tools.calculator.invalidExpression"


def test_pow_within_limit() -> None:
    result = execute_first_party("calculator", args={"expression": "2**10"})
    assert result.ok is True
    assert result.result == {"value": 1024}


def test_sqrt_cbrt_and_constants() -> None:
    root = execute_first_party("calculator", args={"expression": "sqrt(9)"})
    assert root.ok is True
    assert root.result == {"value": 3}
    cube = execute_first_party("calculator", args={"expression": "cbrt(-8)"})
    assert cube.ok is True
    assert cube.result == {"value": -2}
    circle = execute_first_party("calculator", args={"expression": "2*pi"})
    assert circle.ok is True
    assert math.isclose(circle.result["value"], math.tau)


def test_logs_trig_and_factorial() -> None:
    log10 = execute_first_party("calculator", args={"expression": "log(100, 10)"})
    assert log10.ok is True
    assert log10.result == {"value": 2}
    natural = execute_first_party("calculator", args={"expression": "ln(e)"})
    assert natural.ok is True
    assert math.isclose(natural.result["value"], 1)
    sine = execute_first_party("calculator", args={"expression": "sin(0)"})
    assert sine.ok is True
    assert sine.result == {"value": 0}
    fact = execute_first_party("calculator", args={"expression": "factorial(5)"})
    assert fact.ok is True
    assert fact.result == {"value": 120}
    huge = execute_first_party("calculator", args={"expression": "factorial(21)"})
    assert huge.ok is False


def test_negative_sqrt_rejected() -> None:
    result = execute_first_party("calculator", args={"expression": "sqrt(-1)"})
    assert result.ok is False
    assert result.error_key == "tools.calculator.invalidExpression"
