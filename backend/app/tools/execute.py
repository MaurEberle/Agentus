from __future__ import annotations

from typing import Any

from app.common.secrets import mask_obj
from app.tools.calculator_tool import run as run_calculator
from app.tools.datetime_tool import run as run_datetime
from app.tools.http_tool import run as run_http
from app.tools.models import ExecuteResult
from app.tools.web_search_tool import run as run_web_search


def execute_first_party(
    kind: str,
    *,
    config: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
    secret: str | None = None,
) -> ExecuteResult:
    try:
        if kind == "http":
            result = run_http(config, args, secret)
        elif kind == "web_search":
            result = run_web_search(config, args, secret)
        elif kind == "datetime":
            result = run_datetime(config, args)
        elif kind == "calculator":
            result = run_calculator(config, args)
        else:
            return ExecuteResult(ok=False, error_key="tools.unknownKind")
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return ExecuteResult(ok=False, error_key="tools.unknownKind")
    if result.ok:
        result = result.model_copy(update={"result": mask_obj(result.result)})
    return result
