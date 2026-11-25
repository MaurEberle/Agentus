# Architect

The **Architect** is a chat agent that designs a network with you: agents, prompts, models and tools. On request it creates the network or changes an existing one. It knows the node types, fields and tools of the installed app version. The help chatbot explains the app itself; the two are separate.

## Starting

The architect never starts by itself. In the **Architect** module, pick provider, credential (for cloud) and chat model, then click **Start session**.

- **Ollama models** need tool calling and at least 4B parameters; smaller ones or ones without tools are locked. Up to 14B you see a hint.
- **GPU:** A session starts only if the model (and a local embedding model for the examples) fits into free video memory. If video memory and RAM together are enough, the app offers **Start anyway (slow)**.
- **If a network is running**, the app warns clearly before it starts.
- **Help chatbot:** If architect and help chat both run locally, the help chat pauses during the session. The architect has priority.
- **End session** stops an answer in progress and unloads the Ollama model. After **15 minutes** without input the session ends by itself; chat, brief and draft stay, continuing starts it again.

## Brief and draft

- **Brief:** goal, input, output, sources, local or cloud, tools, constraints, each field an entry of its own to expand. The architect fills it in during the conversation; the pencil lets you edit a field (Ctrl+Enter saves). Below, **Prompts** shows the agents' prompts from the draft, formatted for reading.
- **Draft:** shown on the right as a graph. The badge **valid** or **N errors** shows the check; clicking it lists errors and hints. The architect fixes errors itself; after three failed tries it asks you.
- **Building guides:** linear, orchestrator, knowledge chat, router triage. The architect reads the matching one before drafting.

## Reading networks in

**Read in network …** picks a saved network, **to change it** or **as a template** (then a new network is created at the end). This also works in an empty chat, before the session runs. If the architect asks for it, a card appears above the input; nothing is read in before your click.

When changing, the preview marks new nodes green and changed ones yellow; **N changes** below the network name lists them.

**Cloud models** see the structure and prompts of a network only when you explicitly read it in. Folder paths stay hidden from them unless you allow it under **Settings → Architect**.

## Finishing

Once the draft is valid, the architect suggests finishing, or you click **Finish …**. The closing dialog shows summary, structure, for changes the differences to the saved version, and risky parts (unrestricted terminal, file access with delete, HTTP with a credential).

Options: **Set as active**, **Add prompts to the library** (off by default), **Open in the editor afterwards**. Nothing is saved before **Create** or **Apply changes**, and it is saved as a new version with source “Architect”.

- **If the network is running**, nothing is applied.
- **If the network was saved elsewhere since it was read in**, the dialog says so: **Read in again** discards the draft, **Apply anyway** puts it on top as a new version.
- **Undo last apply** brings back the version before the apply, as a new version.

## Research

- **Web search:** its own settings under **Settings → Architect**, separate from the help chat; off by default.
- **Hugging Face:** the architect searches GGUF models and reads quants, sizes and license. You download them yourself under **Models → Hub**.
- **Limits:** tool calls per answer, web searches and Hub calls per session. 0 turns web search or Hub search off.

## Examples

The architect looks for example networks that match the brief. Shipped examples come with a later update. **Use my own networks as examples** (Settings → Architect) takes valid networks only; cloud models see no prompts there. Without an embedding model the architect searches by keywords.

## Sessions

Sessions are listed on the left with chat, brief and draft. **New** opens an empty chat: if a session is running, the new one starts right away on the same model, which stays loaded; otherwise you pick a model and start. **Markdown** exports a session, **Delete** removes it; networks it created stay.
