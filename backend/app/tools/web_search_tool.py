from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.common.http import client
from app.common.secrets import mask_obj
from app.tools.models import ExecuteResult

SEARCH_PROVIDERS = ("brave", "tavily", "exa", "searxng")
_BRAVE = "https://api.search.brave.com/res/v1/web/search"
_TAVILY = "https://api.tavily.com/search"
_EXA = "https://api.exa.ai/search"


def _fail(key: str) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key)


def _clamp_results(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = 5
    return max(1, min(10, number))


def _provider(config: dict[str, Any] | None) -> str:
    raw = (config or {}).get("searchProvider")
    if raw is None or str(raw).strip() == "":
        return "brave"
    name = str(raw).strip().lower()
    return name if name in SEARCH_PROVIDERS else ""


def _base_url(config: dict[str, Any] | None) -> str:
    text = str((config or {}).get("searchBaseUrl") or "").strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text
    return ""


def _items(rows: object, max_results: int, snippet_of) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return items
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "title": str(row.get("title") or ""),
                "url": str(row.get("url") or ""),
                "snippet": snippet_of(row),
            }
        )
    return items


def _snippet_text(row: dict[str, Any]) -> str:
    highlights = row.get("highlights")
    if isinstance(highlights, list) and highlights:
        return str(highlights[0] or "")
    return str(row.get("text") or row.get("content") or row.get("description") or "")


def _request(provider: str, query: str, count: int, secret: str | None, base: str) -> httpx.Response:
    headers = {"Accept": "application/json"}
    with client(timeout_sec=15.0) as http:
        if provider == "brave":
            headers["X-Subscription-Token"] = secret or ""
            return http.get(_BRAVE, params={"q": query, "count": count}, headers=headers)
        if provider == "tavily":
            headers["Authorization"] = f"Bearer {secret or ''}"
            return http.post(
                _TAVILY,
                headers=headers,
                json={"query": query, "max_results": count, "search_depth": "basic", "include_answer": False},
            )
        if provider == "exa":
            headers["x-api-key"] = secret or ""
            return http.post(
                _EXA,
                headers=headers,
                json={
                    "query": query,
                    "numResults": count,
                    "contents": {"highlights": {"maxCharacters": 400}},
                },
            )
        return http.get(f"{base}/search", params={"q": query, "format": "json"}, headers=headers)


def _rows(provider: str, payload: object) -> object:
    if not isinstance(payload, dict):
        return None
    if provider == "brave":
        web = payload.get("web")
        return web.get("results") if isinstance(web, dict) else None
    return payload.get("results")


def run(
    config: dict[str, Any] | None,
    args: dict[str, Any] | None,
    secret: str | None,
) -> ExecuteResult:
    query = "" if args is None else str(args.get("query") or "").strip()
    if not query or len(query) > 500:
        return _fail("tools.webSearch.invalidQuery")
    provider = _provider(config)
    if not provider:
        return _fail("tools.webSearch.unknownProvider")
    base = _base_url(config)
    if provider == "searxng":
        if not base:
            return _fail("tools.webSearch.missingBaseUrl")
    elif not secret:
        return _fail("tools.webSearch.missingCredential")
    count = _clamp_results((config or {}).get("maxResults", 5))
    try:
        response = _request(provider, query, count, secret, base)
    except httpx.TimeoutException:
        return _fail("tools.webSearch.upstream")
    except httpx.HTTPError:
        return _fail("tools.webSearch.upstream")
    if response.status_code in {401, 403}:
        return _fail("tools.webSearch.unauthorized")
    if response.status_code != 200:
        return _fail("tools.webSearch.upstream")
    try:
        payload = response.json()
    except ValueError:
        return _fail("tools.webSearch.upstream")
    items = _items(_rows(provider, payload), count, _snippet_text)
    return ExecuteResult(ok=True, result=mask_obj({"results": items}))
