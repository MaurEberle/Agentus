# Dashboard

The home page shows whether the environment is ready and which network is active.

## Setup card

If Ollama, a model, or WebView2 is missing, the card says so. The installer may pull default models; at runtime the app **never** pulls models silently.

## Status and runtime

Cards for service status (stopped / running), recent runs, and the environment. Runtime ping and model list live under **Settings → Runtime**.

## Data

App data is under the local app folder (`Agentus-Network`), not the program folder. The data directory is shown in **Settings → Data**. Portable zip: data next to the EXE.
