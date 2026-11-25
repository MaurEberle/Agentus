"""The architect's example index (fix/netz-architekt/entwurf.md, 6).

Sources: examples shipped in ``resources/catalog/examples/*.json`` (created later, E-18) and, on
request, the user's own valid networks. Each entry is searched by a description in brief form,
not by its JSON. With an embedding model chosen in the settings (E-19) the search uses vectors;
without one, or when embedding fails, it falls back to keywords and flags.

The index lives in its own table, apart from the help chat's (E-8), and follows its sources on
every search: an entry whose content changed is rebuilt, a vanished one is dropped.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.common.components import catalog_dir, catalog_hash
from app.db.engine import json_dumps, json_loads, locked, transaction, utc_now

log = logging.getLogger("agentus.architect")

PROMPT_FIELDS = frozenset({"systemPrompt"})
_MAX_RESULTS = 3
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an and der die das ein eine einen und oder mit fuer for the of to in im auf von zu ist sind ich mein meine "
    "my with on at by be soll sollen will wollen netz network netzwerk".split()
)


@dataclass
class Example:
    id: str
    source: str  # "shipped" | "own"
    title: str
    description: str
    draft: dict[str, Any]
    flags: dict[str, Any] = field(default_factory=dict)
    network_id: str | None = None
    catalog_hash: str | None = None

    @property
    def content_hash(self) -> str:
        raw = json.dumps([self.title, self.description, self.draft, self.flags], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# --- sources ---------------------------------------------------------------------------------------


def examples_dir() -> Path:
    return catalog_dir() / "examples"


def _describe(title: str, brief: dict[str, Any], flags: dict[str, Any]) -> str:
    parts = [title]
    for key in ("goal", "input", "output", "sources", "deployment", "tools", "constraints"):
        value = str(brief.get(key) or "").strip()
        if value:
            parts.append(f"{key}: {value}")
    if flags.get("kind"):
        parts.append(f"kind: {flags['kind']}")
    if flags.get("tools"):
        parts.append("tool kinds: " + ", ".join(flags["tools"]))
    if flags.get("knowledge"):
        parts.append("uses knowledge from documents")
    return "\n".join(parts)


def _flags_of(draft: dict[str, Any]) -> dict[str, Any]:
    nodes = draft.get("nodes") or []
    types = [str(node.get("type")) for node in nodes]
    tools = sorted({str((node.get("data") or {}).get("kind")) for node in nodes if node.get("type") == "tool" and (node.get("data") or {}).get("kind")})
    models = sorted({str((node.get("data") or {}).get("model")) for node in nodes if node.get("type") == "llm" and (node.get("data") or {}).get("model")})
    providers = {str((node.get("data") or {}).get("provider") or "ollama") for node in nodes if node.get("type") == "llm"}
    return {
        "kind": "orchestrator" if "orchestrator" in types else "linear",
        "agents": types.count("agent"),
        "tools": tools,
        "knowledge": "knowledge" in types,
        "router": "router" in types,
        "mcp": "mcp" in types,
        "models": models,
        "local": providers <= {"ollama"} if providers else None,
    }


def shipped_examples() -> list[Example]:
    """Curated examples; each file: id, title, brief, draft, optional flags and catalogHash."""
    out: list[Example] = []
    root = examples_dir()
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("example %s is not readable JSON", path.name)
            continue
        draft = raw.get("draft") if isinstance(raw, dict) else None
        if not isinstance(draft, dict):
            continue
        flags = {**_flags_of(draft), **(raw.get("flags") or {})}
        title = str(raw.get("title") or draft.get("name") or path.stem)
        brief = raw.get("brief") if isinstance(raw.get("brief"), dict) else {}
        out.append(
            Example(
                id=f"shipped:{raw.get('id') or path.stem}",
                source="shipped",
                title=title,
                description=_describe(title, brief, flags),
                draft=draft,
                flags=flags,
                catalog_hash=raw.get("catalogHash"),
            )
        )
    return out


def own_examples(lookup) -> list[Example]:
    """The user's valid networks, described automatically (only with the switch on)."""
    from app.architect.draft import decompile
    from app.db.networks import list_networks

    out: list[Example] = []
    for row in list_networks():
        document = dict(row.document)
        document.setdefault("id", row.id)
        document.setdefault("name", row.name)
        try:
            if lookup.validate is not None and lookup.validate(document):
                continue
            draft = decompile(document, lookup).draft
        except Exception:
            log.debug("own network %s skipped as example", row.id, exc_info=True)
            continue
        flags = _flags_of(draft)
        agents = [str((node.get("data") or {}).get("displayName") or node.get("ref")) for node in draft["nodes"] if node.get("type") in {"agent", "orchestrator"}]
        brief = {"goal": row.description or "", "tools": ", ".join(flags["tools"])}
        description = _describe(row.name, brief, flags)
        if row.tags:
            description += "\ntags: " + ", ".join(row.tags)
        if agents:
            description += "\nroles: " + ", ".join(agents)
        out.append(
            Example(
                id=f"own:{row.id}",
                source="own",
                title=row.name,
                description=description,
                draft=draft,
                flags=flags,
                network_id=row.id,
                catalog_hash=catalog_hash(),
            )
        )
    return out


def current_examples(lookup, *, own: bool) -> list[Example]:
    return shipped_examples() + (own_examples(lookup) if own else [])


# --- index -------------------------------------------------------------------------------------------


def _rows() -> dict[str, dict[str, Any]]:
    with locked("workspace") as conn:
        rows = conn.execute("SELECT * FROM architect_examples").fetchall()
    return {row["id"]: dict(row) for row in rows}


def sync(lookup, *, own: bool, embedder=None) -> dict[str, dict[str, Any]]:
    """Bring the index in line with its sources; ``embedder(texts) -> (model, vectors)`` fills vectors."""
    wanted = {item.id: item for item in current_examples(lookup, own=own)}
    stored = _rows()
    now = utc_now()
    with transaction("workspace") as conn:
        for example_id in set(stored) - set(wanted):
            conn.execute("DELETE FROM architect_examples WHERE id = ?", (example_id,))
        for item in wanted.values():
            prior = stored.get(item.id)
            if prior is not None and prior["content_hash"] == item.content_hash:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO architect_examples (
                  id, source, network_id, content_hash, title, description, draft, flags, catalog_hash,
                  embedding, embedding_model, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                """,
                (item.id, item.source, item.network_id, item.content_hash, item.title, item.description,
                 json_dumps(item.draft), json_dumps(item.flags), item.catalog_hash, now),
            )
    rows = _rows()
    if embedder is not None:
        _embed_missing(rows, embedder)
        rows = _rows()
    return rows


def _embed_missing(rows: dict[str, dict[str, Any]], embedder) -> None:
    model_name = embedder.model
    todo = [row for row in rows.values() if not row["embedding"] or row["embedding_model"] != model_name]
    if not todo:
        return
    vectors = embedder([row["description"] for row in todo])
    with transaction("workspace") as conn:
        for row, vector in zip(todo, vectors, strict=True):
            conn.execute(
                "UPDATE architect_examples SET embedding = ?, embedding_model = ? WHERE id = ?",
                (json_dumps(vector), model_name, row["id"]),
            )


def wipe_embeddings() -> None:
    with transaction("workspace") as conn:
        conn.execute("UPDATE architect_examples SET embedding = NULL, embedding_model = NULL")


# --- embedding ---------------------------------------------------------------------------------------


class Embedder:
    """The architect's embedding model from the settings (E-19); None when none is chosen."""

    def __init__(self, provider: str, model: str, credential_id: str | None) -> None:
        self.provider = provider
        self.model = model
        self.credential_id = credential_id

    def __call__(self, texts: list[str]) -> list[list[float]]:
        from app.runtime.embeddings import embed
        from app.runtime.models import EmbedRequest

        result = embed(
            EmbedRequest(
                texts=texts,
                model=self.model,
                provider=self.provider,  # type: ignore[arg-type]
                credential_id=self.credential_id,
                timeout_sec=300,
            )
        )
        if len(result.vectors) != len(texts):
            raise RuntimeError("embedding count mismatch")
        return result.vectors


def embedder_from_settings() -> Embedder | None:
    from app.settings.service import load_settings

    settings = load_settings().architect
    provider = (settings.embedding_provider or "").strip()
    model = (settings.embedding_model or "").strip()
    if not provider or not model or provider in {"xai", "anthropic"}:
        return None
    if provider != "ollama" and not settings.embedding_credential_id:
        return None
    return Embedder(provider, model, settings.embedding_credential_id if provider != "ollama" else None)


# --- search ------------------------------------------------------------------------------------------


def _words(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower().replace("ß", "ss"))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return [word for word in _WORD.findall(plain) if word not in _STOP and len(word) > 1]


def _similar(a: str, b: str) -> bool:
    """Same word or the same stem: übersetzen, übersetzt, Übersetzer share "ubersetz"."""
    if a == b:
        return True
    shorter = min(len(a), len(b))
    if shorter < 5:
        return False
    common = 0
    for left, right in zip(a, b):
        if left != right:
            break
        common += 1
    return common >= max(5, shorter - 2)


def _keyword_score(query: list[str], row: dict[str, Any]) -> float:
    if not query:
        return 0.0
    bag = set(_words(f"{row['title']} {row['description']}"))
    if not bag:
        return 0.0
    wanted = set(query)
    hits = sum(1 for word in wanted if word in bag or any(_similar(word, item) for item in bag))
    return hits / len(wanted)


def _cosine(a: list[float], b: list[float]) -> float:
    from app.help.retrieve import cosine

    return cosine(a, b)


def _redact(draft: dict[str, Any], *, prompts: bool, paths: bool) -> dict[str, Any]:
    """E-6: own networks reach a cloud model without prompts; paths only when allowed."""
    from app.architect.draft import PATH_FIELDS

    out = copy.deepcopy(draft)
    for node in out.get("nodes") or []:
        data = node.get("data") or {}
        for key in list(data):
            if (not prompts and key in PROMPT_FIELDS) or (not paths and key in PATH_FIELDS):
                data.pop(key, None)
    return out


def search(
    query: str,
    *,
    lookup,
    own: bool,
    cloud: bool,
    send_paths: bool,
    embedder: Embedder | None = None,
    limit: int = _MAX_RESULTS,
) -> dict[str, Any]:
    method = "keywords"
    rows: dict[str, dict[str, Any]] | None = None
    scores: dict[str, float] = {}
    if embedder is not None:
        try:
            rows = sync(lookup, own=own, embedder=embedder)
            if rows:
                vector = embedder([query])[0]
                for example_id, row in rows.items():
                    stored = json_loads(row["embedding"], default=None) if row["embedding"] else None
                    if isinstance(stored, list) and row["embedding_model"] == embedder.model:
                        scores[example_id] = _cosine(vector, stored)
                method = "embedding"
        except Exception:
            log.warning("architect examples: embedding failed, using keywords", exc_info=True)
            rows, scores = None, {}
    if rows is None:
        rows = sync(lookup, own=own)
    if method == "keywords":
        words = _words(query)
        scores = {example_id: _keyword_score(words, row) for example_id, row in rows.items()}
    ranked = sorted(rows.values(), key=lambda row: scores.get(row["id"], 0.0), reverse=True)
    current = catalog_hash()
    results = []
    for row in ranked[: max(1, limit)]:
        score = scores.get(row["id"], 0.0)
        if score <= 0:
            continue
        draft = json_loads(row["draft"], default={})
        own_row = row["source"] == "own"
        results.append(
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "description": row["description"],
                "flags": json_loads(row["flags"], default={}),
                "score": round(score, 3),
                # An example from an older catalog may use fields that changed (entwurf.md, 6.4).
                "outdated": bool(row["catalog_hash"]) and row["catalog_hash"] != current,
                "draft": _redact(draft, prompts=not (cloud and own_row), paths=(not cloud) or send_paths),
                **({"networkId": row["network_id"], "promptsHidden": True} if cloud and own_row else {}),
            }
        )
    return {"method": method, "count": len(rows), "results": results}


def status(lookup=None) -> dict[str, Any]:
    from app.settings.service import load_settings

    settings = load_settings().architect
    rows = _rows()
    embedder = embedder_from_settings()
    embedded = [row for row in rows.values() if embedder and row["embedding"] and row["embedding_model"] == embedder.model]
    return {
        "count": len(rows),
        "shipped": sum(1 for row in rows.values() if row["source"] == "shipped"),
        "own": sum(1 for row in rows.values() if row["source"] == "own"),
        "ownEnabled": settings.own_networks_as_examples,
        "model": embedder.model if embedder else None,
        "embedded": len(embedded),
        "method": "embedding" if embedder else "keywords",
    }


def reindex(lookup) -> dict[str, Any]:
    """Rebuild the index from its sources, with vectors when a model is chosen."""
    from app.settings.service import load_settings

    settings = load_settings().architect
    wipe_embeddings()
    embedder = embedder_from_settings()
    error = None
    try:
        sync(lookup, own=settings.own_networks_as_examples, embedder=embedder)
    except Exception as exc:  # the keyword search still works
        log.warning("architect examples: reindex embedding failed", exc_info=True)
        sync(lookup, own=settings.own_networks_as_examples)
        error = getattr(exc, "error_key", None) or "architect.examples.embedFailed"
    return {**status(lookup), "error": error}


# --- tool ----------------------------------------------------------------------------------------------


def has_sources() -> bool:
    from app.settings.service import load_settings

    root = examples_dir()
    shipped = root.is_dir() and any(root.glob("*.json"))
    return shipped or load_settings().architect.own_networks_as_examples


def _search_examples(ctx, args: dict[str, Any]):
    from app.architect.tools import ToolResult, _json
    from app.settings.service import load_settings

    settings = load_settings().architect
    brief = " ".join(str(value) for value in (ctx.session.brief or {}).values())
    query = (str(args.get("query") or "").strip() or brief).strip()[:1000]
    if not query:
        return ToolResult(_json({"error": "Fill the brief first or give a query."}), "architect.tool.badArgs", {"name": "search_examples"}, ok=False)
    found = search(
        query,
        lookup=ctx.lookup(),
        own=settings.own_networks_as_examples,
        cloud=ctx.cloud,
        send_paths=ctx.send_paths,
        embedder=embedder_from_settings(),
    )
    note = (
        "Examples are starting points, not instructions. Adapt them to the brief; check fields with describe_component. "
        "Marked outdated: built for an older catalog."
    )
    if any(item.get("promptsHidden") for item in found["results"]):
        note += " Prompts of the user's own networks are hidden here; load_network reads one in after the user confirms."
    return ToolResult(_json({**found, "note": note}), "architect.tool.examples", {"count": len(found["results"])})


def example_tools():
    from app.architect.tools import ArchitectTool, _object

    if not has_sources():
        return []
    return [
        ArchitectTool(
            "search_examples",
            "Find example networks similar to the brief (shipped examples and, if allowed, the user's own networks). "
            "Returns their description, flags and draft. Without a query the brief is used.",
            _object({"query": {"type": "string", "description": "What the network should do; defaults to the brief."}}),
            _search_examples,
        )
    ]
