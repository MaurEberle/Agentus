# Guide: linear network (a chain of agents)

## When it fits
- The work has fixed steps in a fixed order: summarize → translate → format, research → write.
- No step needs to send work back, and nobody has to judge between rounds.
- One message in, one result out. Follow-up questions are not needed during the run.

If steps must be repeated, reviewed or chosen by situation, use the orchestrator guide instead.

## Structure
```
chat ─▶ agent A ─▶ agent B ─▶ … ─▶ end
          ▲           ▲
         llm      llm, tools, knowledge
```
- One `chat_input` at the start (or none: then the first agent starts the chain).
- Agents in a row, each with exactly one incoming message edge.
- At least one `end`; the last agent's message goes there.
- Every agent needs exactly one LLM edge. One `llm` node may serve all agents.
- Tools and knowledge connect to the agent that needs them, not to all.
- A `router` splits the chain by text: each branch and the default need exactly one edge.

## Draft skeleton
```json
{
  "name": "Summary and translation",
  "nodes": [
    {"ref": "chat", "type": "chat_input", "data": {"placeholder": "Paste the text"}},
    {"ref": "summarizer", "type": "agent", "data": {"displayName": "Summarizer", "systemPrompt": "…"}},
    {"ref": "translator", "type": "agent", "data": {"displayName": "Translator", "systemPrompt": "…"}},
    {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "<installed tag>"}},
    {"ref": "end", "type": "end"}
  ],
  "links": [["chat", "summarizer"], ["summarizer", "translator"], ["translator", "end"],
            ["model", "summarizer"], ["model", "translator"]]
}
```

## Prompt template for a chain agent
```
You are <role> in a chain. You get <what arrives> from <previous step or the user>.
Task: <one clear task>.
Rules: <quality bar, what to leave out, language>.
Output: <exact format the next step expects>. Write only the output, no preamble.
```
- The next agent sees only what this agent writes. Say exactly what to hand on.
- Name the output format when a router follows (for example "first line: URGENT or NORMAL"); route on `firstLine`.

## Common mistakes
- An agent without an LLM edge, or with two.
- The chain does not reach an end.
- A router branch without an edge, or a default without an edge.
- Tools on agents that do not need them; a model without tool calling on an agent with tools.
