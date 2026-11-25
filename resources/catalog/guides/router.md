# Guide: router triage (one input, different paths)

## When it fits
- Incoming messages fall into a few kinds that need different handling: bug report vs. question vs. order, urgent vs. normal, German vs. English.
- The kind can be told from the text, ideally from a keyword that a first agent writes.
- Each path is a short chain of its own and ends in an `end`.

If the paths must talk to each other or loop back, use the orchestrator guide instead. A router after an orchestrator may only lead to ends.

## Structure
```
chat ─▶ classifier ─▶ router ─┬─ branch "bug" ──▶ bug agent ──▶ end
                              ├─ branch "question" ▶ helper ──▶ end
                              └─ default ─────────▶ fallback ─▶ end
```
- A `router` has one message input and one output per branch plus `default`. Branches are checked in order; the first match wins.
- Each branch has a unique `name`, a `match` (`contains`, `startsWith`, `firstLine`, `regex`) and a `pattern` (at most 200 characters). Regular expressions must be valid.
- Every branch and the default need exactly one edge. In the draft, a link from a router names its branch as third entry: `["triage", "bugfixer", "bug"]`, or `"default"`.
- Router outputs lead to an agent, a router or an end.
- The most robust setup: a small classifier agent writes exactly one keyword in its first line; the router matches with `firstLine`.

## Draft skeleton
```json
{
  "name": "Support triage",
  "nodes": [
    {"ref": "chat", "type": "chat_input", "data": {"placeholder": "Describe your request"}},
    {"ref": "classifier", "type": "agent", "data": {"displayName": "Classifier", "systemPrompt": "…"}},
    {"ref": "triage", "type": "router", "data": {"displayName": "Triage", "branches": [
      {"name": "bug", "match": "firstLine", "pattern": "BUG"},
      {"name": "question", "match": "firstLine", "pattern": "QUESTION"}
    ]}},
    {"ref": "bugfixer", "type": "agent", "data": {"displayName": "Bug triage", "systemPrompt": "…"}},
    {"ref": "helper", "type": "agent", "data": {"displayName": "Helper", "systemPrompt": "…"}},
    {"ref": "fallback", "type": "agent", "data": {"displayName": "Fallback", "systemPrompt": "…"}},
    {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "<installed tag>"}},
    {"ref": "end", "type": "end"}
  ],
  "links": [["chat", "classifier"], ["classifier", "triage"],
            ["triage", "bugfixer", "bug"], ["triage", "helper", "question"], ["triage", "fallback", "default"],
            ["bugfixer", "end"], ["helper", "end"], ["fallback", "end"],
            ["model", "classifier"], ["model", "bugfixer"], ["model", "helper"], ["model", "fallback"]]
}
```

## Prompt template for the classifier
```
Classify the message. Write exactly one word in the first line: BUG, QUESTION or OTHER.
From the second line on, repeat the message unchanged so the next agent has it.
BUG: something is broken or behaves wrongly. QUESTION: the user wants to know how something works.
OTHER: anything else.
```
- The classifier can use a small, fast model; the path agents need the stronger one.

## Common mistakes
- A branch or the default without an edge, or with two.
- Patterns that overlap; the first match wins, so put the most specific branch first.
- Matching on free text with `contains` when a keyword in the first line would be exact.
- A classifier that drops the original message: the next agent sees only what it writes.
