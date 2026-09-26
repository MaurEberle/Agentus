# Términos

Glosario breve para el chat de ayuda y el editor.

## Grafo / red

Documento guardado de nodos y aristas. Lo editas en el editor y gestionas copias en la biblioteca. La red **activa** es la de la selección rápida — solo esa arranca **Iniciar**.

## Ejecución (run)

Una pasada del grafo activo. Corre como máximo **una**. Iniciar y detener en el encabezado. Resultados: en curso, éxito, error, cancelado, tiempo agotado.

## Nodos y aristas

Piezas (chat, orquestador, agente, LLM, herramienta, conocimiento, enrutador, fin) y conexiones tipadas. Flechas arbitrarias entre cajas no valen.

## Agente

Nodo con prompt de sistema. Modelo, mensaje, herramientas y conocimiento llegan por puertos. Sin orquestador lo arranca el mensaje, y mensaje o transferencia siguen con la respuesta. Con orquestador cuelga de su propio canal: un encargo entra, un resultado vuelve.

## Nodo LLM

Elige proveedor y modelo. Local vía Ollama; si no, nube más credencial.

## Chat

Única entrada de texto de usuario en la ejecución. Como máximo una por red. El chat de supervisión escribe aquí. Con orquestador la conversación sigue abierta en varios mensajes.

## Orquestador

Nodo con su propio LLM. Es la única voz del chat de la ejecución, hace preguntas y llama a los agentes conectados de uno en uno por un canal cada uno. Como máximo uno. El chat solo se conecta a él. Su salida de mensaje va a Fin o a un enrutador. No ves los textos de los agentes ni las órdenes internas como burbujas. La app adjunta el último resultado al siguiente encargo. Un agente está en el canal o en la cadena de mensajes. Las herramientas pueden conectarse a su puerto Herramienta. Las llama él mismo.

## Herramienta

First-party (HTTP, búsqueda web, fecha/hora, calculadora, acceso a archivos) o MCP. El acceso a archivos se queda en una carpeta raíz, no en la raíz de la unidad. Configuración en el inspector, ejecución solo durante el run.

## Conocimiento (red)

Nodo de conocimiento: una carpeta de textos para la red. Puede estar en cualquier sitio salvo una raíz de unidad o de sistema y el corpus de ayuda. Modelo de embeddings propio, índice, topK y puntuación. **No** es el corpus de ayuda. Al iniciar ves la indexación; un índice ya actual se omite.

## Ayuda-RAG

Documentos en la carpeta de ayuda de la carpeta de datos (guías predeterminadas más tus Markdown). Solo el chatbot de ayuda. Tras cambios, reconstruye el índice en Ajustes → Chat de ayuda.

## Credencial

Clave guardada en el almacén de Windows. En las listas solo máscara. En el grafo solo el ID/elección, nunca el secreto. La exportación no incluye contraseñas.

## MCP

Model Context Protocol: servidores de herramientas externos. Créalos y actívalos en Ajustes, conéctalos en el grafo como nodo de herramienta de tipo MCP. La ayuda no usa MCP.

## Proveedor

En la lista: `ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (nube: primero la credencial, luego la lista de modelos). Embeddings: Ollama, OpenAI, Gemini. `openai_compat` sigue valiendo en grafos y credenciales antiguos, pero ya no está en la lista de modelos.

## Ollama

Servicio aparte para modelos locales. La app es el cliente. Si está instalado, la dirección es local y el puerto no responde, la app lo arranca y no lo detiene. El setup puede crear Ollama, esperar un momento y cargar dos modelos pequeños por defecto si responde.

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
