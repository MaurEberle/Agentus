# Agentus Network — guía rápida

Agentus Network es una **aplicación de escritorio local**. En este PC construyes redes de agentes, modelos de idioma y herramientas, inicias **una** ejecución y la ves en vivo. La interfaz pertenece a la propia app (su ventana), no a Chrome ni a una página `file://`.

Ollama es un **servicio aparte**. Cerrar o desinstalar Agentus Network no detiene Ollama ni borra modelos. Si Ollama está instalado en este PC, la dirección en Ajustes es local y el servicio está parado, la app lo arranca al abrir la ventana.

## Ventana y navegación

A la izquierda (en el teléfono: menú hamburguesa):

- **Dashboard** — inicio, configuración, red activa, últimas ejecuciones
- **Red** — editor (un grafo)
- **Biblioteca** — todas las redes guardadas
- **Supervisión** — ejecución en vivo
- **Historial** — ejecuciones terminadas y estadísticas

**Ajustes** están en el encabezado (engranaje), no en la navegación izquierda.

En el encabezado también: **Iniciar** / **Detener**, **selección rápida** de la red activa, campana (notificaciones), claro/oscuro/sistema, idioma (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية) y botones de ventana (minimizar, maximizar, cerrar).

Arrastra el logotipo o el encabezado vacío para mover la ventana. Iniciar, Detener, la selección rápida y los botones de la derecha no son zonas de arrastre.

## Primer recorrido

1. Ollama debe ser alcanzable. La app arranca sola un servicio local si está instalado pero parado. El setup puede crear Ollama, iniciarlo un momento en segundo plano y traer los modelos pequeños `nomic-embed-text` y `llama3.2:1b`, solo si Ollama responde. Un setup silencioso sin el interruptor de modelos no descarga nada. Una descarga fallida termina el setup igual con éxito.
2. En **Ajustes → Runtime** comprueba la conexión; la lista de modelos no debe estar vacía.
3. En **Ajustes → Chat de ayuda** elige proveedor y modelo de chat (predeterminado: Ollama + `llama3.2:1b`). Los embeddings son **otro** modelo (`nomic-embed-text`).
4. En la **Biblioteca** o en el editor crea una red, guárdala y **actívala** en la selección rápida.
5. **Iniciar** en el encabezado. La ejecución se ve en **Supervisión**.

El panel muestra los pasos que faltan como tarjetas de configuración.

## Una red mínima

En el editor (**Red**) al menos:

1. **Chat** (`chat_input`) — como máximo una
2. **Agente** — prompt de sistema
3. **LLM** — proveedor y modelo
4. **Fin** (`end`) — al menos uno

Conexiones (puertos tipados, no flechas arbitrarias):

- Chat **Mensaje** → Agente **Mensaje**
- LLM **LLM** → Agente **LLM**
- Agente **Mensaje** → Fin

**Orquestador** opcional: el chat solo al orquestador, un LLM al orquestador, un **Canal** del orquestador al canal de cada agente y **Mensaje** del orquestador a **Fin**. Es la única voz del chat de la ejecución, hace preguntas y llama a los agentes de uno en uno. Los textos de los agentes y las órdenes internas no aparecen como burbujas. La app adjunta el último resultado al siguiente encargo; no hace falta pegarlo en el chat. El chat sigue abierto hasta que él termina la ejecución. Sin orquestador cada agente es su propia cadena por mensaje y transferencia. Un agente está en el canal o en la cadena, nunca en ambos.

Opcional: **Herramienta** al puerto **Herramienta** del agente o del orquestador, **Conocimiento** a **Conocimiento**. Guardar. En la **Biblioteca**, «Definir como activa» si la selección rápida aún no lo está.

## Iniciar y detener

**Iniciar** lanza **una** ejecución de la red **activa** (selección rápida). Nunca corre una segunda red en paralelo. Un segundo inicio se rechaza hasta **Detener**.

**Detener** cancela la ejecución (resultado **Cancelado**, no **Error**). Ollama sigue en marcha.

Sin red activa no arranca nada. Una red inválida (error de validación, modelo ausente) conviene comprobarla en el editor antes de iniciar.

Mientras corre la red activa, **ese** documento del editor es de solo lectura. Puedes seguir viendo otras redes; borrar la red en ejecución en la biblioteca está bloqueado.

Cerrar la ventana termina la ejecución y la app. Ollama sigue vivo.

## El chat de ayuda no es el chat de la red

Abajo a la derecha: burbuja = **ayuda de la app** (esta guía, términos del grafo, búsqueda web opcional). El onboarding lo explica la primera vez.

En **Supervisión**, la pestaña **Chat** = **chat de la ejecución** del grafo (nodo Chat). Sin orquestador es la entrada a los agentes. Con orquestador es la conversación: puede preguntarte antes de llamar a un agente.

No comparten **historial**, herramientas ni credenciales. La ayuda **no** usa servidores MCP.

## Ollama y la nube

- **Local:** Ollama, en Ajustes como Runtime. Allí listas y pruebas modelos. La app **no** descarga modelos en silencio en tiempo de ejecución.
- **Nube:** credenciales en **Ajustes → Credenciales** (xAI, OpenAI, Claude, Gemini, búsqueda web, …). En el nodo LLM eliges Ollama, xAI, OpenAI, Claude o Gemini. Nube sin credencial adecuada no es válida. Las listas muestran solo una **máscara**, nunca el secreto. Los nodos LLM y la ayuda apuntan a la credencial por nombre, no con la clave en el grafo.

Una URL base compatible con OpenAI ya no se ofrece en Runtime. Las credenciales de ese tipo que ya existan siguen en Credenciales.

## Una instancia

Un segundo arranque trae al frente la ventana existente. No hay un segundo backend ni una segunda ejecución.

## Portátil e instalada

La app instalada guarda datos en la carpeta local **Agentus-Network**, no junto al programa. La variante portátil (archivo `portable.txt` junto al EXE) guarda datos **junto al EXE**. Con Portable debes aportar tú WebView2 y Ollama.
