# Agentus Network — guía rápida

Agentus Network es una **aplicación de escritorio local**. En este PC construyes redes de agentes, modelos de idioma y herramientas, inicias **una** ejecución y la ves en vivo. La interfaz pertenece a la propia app (su ventana), no a Chrome ni a una página `file://`.

Ollama es un **servicio aparte**. Cerrar o desinstalar Agentus Network no detiene Ollama ni borra modelos.

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

1. Ollama debe estar en marcha (el instalador puede crearlo y traer los modelos pequeños `nomic-embed-text` y `llama3.2:1b`).
2. En **Ajustes → Runtime** comprueba la conexión; la lista de modelos no debe estar vacía.
3. En **Ajustes → Chat de ayuda** elige proveedor y modelo de chat (predeterminado: Ollama + `llama3.2:1b`). Los embeddings son **otro** modelo (`nomic-embed-text`).
4. En la **Biblioteca** o en el editor crea una red, guárdala y **actívala** en la selección rápida.
5. **Iniciar** en el encabezado. La ejecución se ve en **Supervisión**.

El panel muestra los pasos que faltan como tarjetas de configuración.

## Una red mínima

En el editor (**Red**) al menos:

1. **Entrada de chat** (`chat_input`) — como máximo una
2. **Agente** — prompt de sistema
3. **LLM** — proveedor y modelo
4. **Fin** (`end`) — al menos uno

Conexiones (puertos tipados, no flechas arbitrarias):

- Entrada de chat **Mensaje** → Agente **Mensaje**
- LLM **LLM** → Agente **LLM**
- Agente **Mensaje** → Fin

Opcional: **Herramienta** al puerto **Herramienta** del agente, **Conocimiento** a **Conocimiento**. Guardar. En la **Biblioteca**, «Definir como activa» si la selección rápida aún no lo está.

## Iniciar y detener

**Iniciar** lanza **una** ejecución de la red **activa** (selección rápida). Nunca corre una segunda red en paralelo. Un segundo inicio se rechaza hasta **Detener**.

**Detener** cancela la ejecución (resultado **Cancelado**, no **Error**). Ollama sigue en marcha.

Sin red activa no arranca nada. Una red inválida (error de validación, modelo ausente) conviene comprobarla en el editor antes de iniciar.

Mientras corre la red activa, **ese** documento del editor es de solo lectura. Puedes seguir viendo otras redes; borrar la red en ejecución en la biblioteca está bloqueado.

Cerrar la ventana termina la ejecución y la app. Ollama sigue vivo.

## El chat de ayuda no es el chat de la red

Abajo a la derecha: burbuja = **ayuda de la app** (esta guía, términos del grafo, búsqueda web opcional). El onboarding lo explica la primera vez.

En **Supervisión**, la pestaña **Chat** = **chat de la ejecución** del grafo (nodo entrada de chat). Habla con la red de agentes.

No comparten **historial**, herramientas ni credenciales. La ayuda **no** usa servidores MCP.

## Ollama y la nube

- **Local:** Ollama, en Ajustes como Runtime. Allí listas y pruebas modelos. La app **no** descarga modelos en silencio en tiempo de ejecución.
- **Nube:** credenciales en **Ajustes → Credenciales** (xAI, compatible con OpenAI, búsqueda web, …). Las listas muestran solo una **máscara**, nunca el secreto. Los nodos LLM y la ayuda apuntan a la credencial por nombre, no con la clave en el grafo.

Compatible con OpenAI (por ejemplo un servidor local) necesita la URL base en **Runtime** y a menudo una credencial.

## Una instancia

Un segundo arranque trae al frente la ventana existente. No hay un segundo backend ni una segunda ejecución.

## Portátil e instalada

La app instalada guarda datos en la carpeta local **Agentus-Network**, no junto al programa. La variante portátil (archivo `portable.txt` junto al EXE) guarda datos **junto al EXE**. Con Portable debes aportar tú WebView2 y Ollama.
