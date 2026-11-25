# Guide: knowledge chat (questions about the user's documents)

## When it fits
- The user wants answers from their own files: manuals, notes, contracts, code, exported pages.
- Answers must stay close to the sources and name them.
- The documents live in one folder (subfolders are fine).

If the answers need fresh facts from the web, add a `web_search` tool. If several specialists must work on the documents, combine this with the orchestrator guide: the knowledge node connects to the agent that reads, not to the chief.

## Structure
```
chat ─▶ answerer ─▶ end
          ▲   ▲
        llm  knowledge (folder, embedding model)
```
- One `knowledge` node per folder. It connects only to the `knowledge` input of an agent.
- The knowledge node needs `sourcePath` (a folder, not a drive or system root, not the app's data folder) and an embedding model: `embeddingProvider` and `embeddingModel` (with Ollama for example an installed embedding model such as nomic-embed-text). Cloud embeddings need `embeddingCredential`.
- `topK` (passages per search, 1–20) and `scoreThreshold` (0–1) tune recall. Start with topK 5 and no threshold.
- The index is built in the editor (Reindex) before the first run. Tell the user.
- The answering agent needs an LLM edge; a model with a large context helps when topK is high.

## Draft skeleton
```json
{
  "name": "Manual questions",
  "nodes": [
    {"ref": "chat", "type": "chat_input", "data": {"placeholder": "Ask about the manual"}},
    {"ref": "answerer", "type": "agent", "data": {"displayName": "Answerer", "systemPrompt": "…"}},
    {"ref": "manual", "type": "knowledge", "data": {"displayName": "Manual", "sourcePath": "<folder the user names>", "embeddingProvider": "ollama", "embeddingModel": "<installed embedding model>"}},
    {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "<installed tag>"}},
    {"ref": "end", "type": "end"}
  ],
  "links": [["chat", "answerer"], ["model", "answerer"], ["manual", "answerer"], ["answerer", "end"]]
}
```

## Prompt template for the answering agent
```
You answer questions about <what the documents are> using the passages from your knowledge search.
Search first; answer only from what you found. If the passages do not answer the question, say so
and say what is missing. Quote short key phrases and name the file each fact comes from.
Answer in <language>, <length>.
```

## Common mistakes
- No folder, a drive root, or the app's data folder as `sourcePath`.
- Knowledge connected to the orchestrator or to an LLM instead of an agent's `knowledge` input.
- An embedding model that is not installed, or a chat model used as embedding model.
- Forgetting to build the index before the first run.
- Promising answers beyond the documents; the prompt must allow "not in the documents".
