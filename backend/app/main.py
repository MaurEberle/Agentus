"""Process entry (`python -m app.main`).

Bind, ``create_app()``, and ``GET /api/health`` land in the HTTP-layer prompt.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "Agentus Network API is not serving yet. "
        "Next: python_backend_persistenz.md, then python_backend_http.md "
        "(GET /api/health on 127.0.0.1:8765)."
    )


if __name__ == "__main__":
    main()
