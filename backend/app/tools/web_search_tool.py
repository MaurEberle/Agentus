from __future__ import annotations

from typing import Any

import httpx

from app.common.http import client
from app.common.secrets import mask_obj
from app.tools.models import ExecuteResult

_BRAVE = "https://api.search.brave.com/res/v1/web/search"


def _clamp_results(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = 5
    return max(1, min(10, number))


def run(
    config: dict[str, Any] | None,
    args: dict[str, Any] | None,
    secret: str | None,
) -> ExecuteResult:
    query = "" if args is None else str(args.get("query") or "").strip()
    if not query or len(query) > 500:
        return ExecuteResult(ok=False, error_key="tools.webSearch.invalidQuery")
    if not secret:
        return ExecuteResult(ok=False, error_key="tools.webSearch.missingCredential")
    max_results = _clamp_results((config or {}).get("maxResults", 5))
    try:
        with client(timeout_sec=15.0) as http:
            response = http.get(
                _BRAVE,
                params={"q": query, "count": max_results},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": secret,
                },
            )
    except httpx.TimeoutException:
        return ExecuteResult(ok=False, error_key="tools.webSearch.upstream")
    except httpx.HTTPError:
        return ExecuteResult(ok=False, error_key="tools.webSearch.upstream")
    if response.status_code in {401, 403}:
        return ExecuteResult(ok=False, error_key="tools.webSearch.unauthorized")
    if response.status_code != 200:
        return ExecuteResult(ok=False, error_key="tools.webSearch.upstream")
    try:
        payload = response.json()
    except ValueError:
        return ExecuteResult(ok=False, error_key="tools.webSearch.upstream")
    web = payload.get("web") if isinstance(payload, dict) else None
    raw_results = web.get("results") if isinstance(web, dict) else None
    items: list[dict[str, str]] = []
    if isinstance(raw_results, list):
        for row in raw_results[:max_results]:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "title": str(row.get("title") or ""),
                    "url": str(row.get("url") or ""),
                    "snippet": str(row.get("description") or ""),
                }
            )
    return ExecuteResult(ok=True, result=mask_obj({"results": items}))
