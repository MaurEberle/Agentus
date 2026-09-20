# Términos

Glosario breve para el chat de ayuda y el editor.

## Grafo / red

Documento guardado de nodos y aristas. Lo editas en el editor y gestionas copias en la biblioteca. La red **activa** es la de la selección rápida — solo esa arranca **Iniciar**.

## Ejecución (run)

Una pasada del grafo activo. Corre como máximo **una**. Iniciar y detener en el encabezado. Resultados: en curso, éxito, error, cancelado, tiempo agotado.

## Nodos y aristas

Piezas (entrada de chat, agente, LLM, herramienta, conocimiento, enrutador, fin) y conexiones tipadas. Flechas arbitrarias entre cajas no valen.

## Agente

Nodo con prompt de sistema. Modelo, mensaje, herramientas y conocimiento llegan por puertos, no como claves embebidas.

## Nodo LLM

Elige proveedor y modelo. Local vía Ollama, si no nube o URL compatible con OpenAI más credencial.

## Entrada de chat

Única entrada de texto de usuario en la ejecución. Como máximo una por red. El chat de supervisión escribe aquí.

## Herramienta

First-party (HTTP, búsqueda web, fecha/hora, calculadora) o MCP. Configuración en el inspector, ejecución solo en el run.

## Conocimiento (red)

Nodo knowledge: carpeta **bajo** la carpeta de datos de la app. Índice propio, topK y puntuación. **No** es el corpus de ayuda. No es la raíz de la unidad.

## Ayuda-RAG

Documentos en la carpeta de ayuda de la carpeta de datos (guías predeterminadas más tus Markdown). Solo el chatbot de ayuda. Tras cambios, reconstruye el índice en Ajustes → Chat de ayuda.

## Credencial

Clave guardada en el almacén de Windows. En las listas solo máscara. En el grafo solo el ID/elección, nunca el secreto. La exportación no incluye contraseñas.

## MCP

Model Context Protocol: servidores de herramientas externos. Créalos y actívalos en Ajustes, conéctalos en el grafo como nodo de herramienta de tipo MCP. La ayuda no usa MCP.

## Proveedor

`ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (nube, primero la clave API, luego la lista de modelos), `openai_compat` (API HTTP compatible propia, p. ej. LM Studio).

## Ollama

Servicio aparte para modelos locales. La app es el cliente. El setup puede crear Ollama y dos modelos pequeños por defecto. Cerrar la app deja Ollama en marcha.

## Panel, supervisión, historial

Panel = resumen y configuración. Supervisión = en vivo. Historial = archivo. No es la misma página tres veces.

## Válido / inválido

Validación del grafo. Inválido se puede guardar, pero no sirve para iniciar. Solo una red válida se puede definir como activa.

## Selección rápida

Elección en el encabezado de la red activa. Equivale a «Definir como activa» en la biblioteca.

## Modo económico

La ayuda pasa al modelo de reserva si el principal no responde. El panel puede mostrarlo en Entorno.

## Portátil

`portable.txt` junto al EXE: datos junto a la aplicación. Copia instalada: datos en la carpeta de la app, programas aparte.
