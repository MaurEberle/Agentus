from __future__ import annotations

import logging
from typing import Any

from app.common.secrets import mask_content_obj
from app.tools.calculator_tool import run as run_calculator
from app.tools.datetime_tool import run as run_datetime
from app.tools.file_access_tool import run as run_file_access
from app.tools.terminal_tool import run as run_terminal
from app.tools.zip_tool import run as run_zip
from app.tools.http_tool import run as run_http
from app.tools.models import ExecuteResult
from app.tools.web_search_tool import run as run_web_search

log = logging.getLogger(__name__)


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
        elif kind == "file_access":
            result = run_file_access(config, args)
        elif kind == "terminal":
            result = run_terminal(config, args)
        elif kind == "zip":
            result = run_zip(config, args)
        else:
            return ExecuteResult(ok=False, error_key="tools.unknownKind")
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        # N6: a bug inside a tool is not an unknown tool kind. Keep the traceback
        # in the app log; the model only learns that the tool itself failed.
        log.exception("tool %s raised", kind)
        return ExecuteResult(
            ok=False,
            error_key="tools.internalError",
            result={"detail": f"The {kind} tool failed internally ({type(exc).__name__}). Try another way."},
        )
    if result.ok:
        # Narrow mask: the model reads this and may write it back (H5). Real secrets
        # and key formats go; source code like f"Bearer {token}" stays intact.
        result = result.model_copy(update={"result": mask_content_obj(result.result)})
    return result
