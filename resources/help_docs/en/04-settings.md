# Settings

## Credentials

Create, rename, delete. Lists show a **mask** only, never the secret. Delete is blocked if help, a network, or MCP uses the credential.

## Data folder

Change only when no run is active. Drive roots are invalid. Portable mode makes the path read-only.

## Help profile

Help chat model and **embeddings** are separate. Embeddings (default `nomic-embed-text`) are not the chat model. After corpus changes: **Reindex** in the help section.

## MCP

Recipes are templates, not binaries. Servers default to off. The app does not spawn MCP at launch — only when a run needs connected servers.
