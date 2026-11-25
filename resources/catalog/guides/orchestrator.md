# Guide: orchestrator network (a chief with agents)

## When it fits
- The work needs planning, several roles, review rounds or rework: coding with tests and review, research with fact checks, data cleaning with checks.
- The user may ask follow-up questions or the chief may need to ask the user.
- The order of steps depends on intermediate results.

For fixed steps in a fixed order, the linear guide is simpler and cheaper.

## Structure
```
chat ─▶ orchestrator ─channel─▶ agent A
            │        ─channel─▶ agent B
            ▼
           end
llm ─▶ orchestrator, llm ─▶ agents; tools ─▶ the agents (and the chief) that need them
```
- Exactly one `orchestrator`. The chat connects only to it.
- One channel from the orchestrator to every agent (link orchestrator → agent). No message edges between agents.
- The orchestrator's message output goes to an `end` (or to a router whose outputs lead only to ends).
- Every agent and the orchestrator need exactly one LLM edge. The chief usually gets the strongest model; agents may share one.
- Tools connect to the agents that use them. The chief may read files itself at any time; changing files, the terminal and other tools it uses only after an agent call failed.

## Draft skeleton
```json
{
  "name": "Coding team",
  "nodes": [
    {"ref": "chat", "type": "chat_input", "data": {"placeholder": "What should be built?"}},
    {"ref": "chief", "type": "orchestrator", "data": {"displayName": "Chief", "systemPrompt": "…"}},
    {"ref": "coder", "type": "agent", "data": {"displayName": "Coder", "systemPrompt": "…"}},
    {"ref": "tester", "type": "agent", "data": {"displayName": "Tester", "systemPrompt": "…"}},
    {"ref": "files", "type": "tool", "data": {"kind": "file_access", "rootPath": "<project folder>", "allowWrite": true}},
    {"ref": "shell", "type": "tool", "data": {"kind": "terminal", "rootPath": "<project folder>", "terminalPrograms": ["git", "python"]}},
    {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "<installed tag with tools>"}},
    {"ref": "end", "type": "end"}
  ],
  "links": [["chat", "chief"], ["chief", "coder"], ["chief", "tester"], ["chief", "end"],
            ["model", "chief"], ["model", "coder"], ["model", "tester"],
            ["files", "coder"], ["files", "tester"], ["shell", "tester"]]
}
```

## Prompt template for the chief (a briefing, not a script)
```
You lead a team for <goal>. The user talks to you in the chat.
Team: <agent> does <role>; <agent> does <role>. Give each task to the agent whose role fits.
Quality bar: <what done means, how to check it>.
Work in small, checkable tasks. After each result decide: next task, rework, ask the user, or finish.
Ask the user only when a decision is theirs (scope, taste, missing facts).
Finish with a short summary: what was done, what is open.
```
The run adds the agents, their tools and the limits to the chief's prompt itself; do not repeat them.

## Prompt template for an agent on a channel
```
You are the <role> of a team. Tasks come from the chief.
Do exactly the task you get. <Standards for this role.>
Report back: what you did, the result (or the files you changed), and anything that blocks you.
```

## Limits worth setting
- `maxAgentCalls` (unset 50): agent calls per run; raise it for long builds.
- `agentMissLimit` (unset 2): failed calls in a row before the chief takes the task.
- `maxToolCalls` on agents (unset 100): tool calls per task.

## Common mistakes
- An agent without a channel, or with a message edge from the chat.
- The chat connected to an agent besides the orchestrator.
- The orchestrator without a path to an end.
- Agents with overlapping roles; the chief then cannot choose.
- A model without tool calling for agents with tools.
