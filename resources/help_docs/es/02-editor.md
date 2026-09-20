# Editor y biblioteca

El editor en **Red** edita **un** documento de grafo. La **Biblioteca** es el catálogo: lista, importar, borrar, activar. El lienzo existe solo en el editor, no en Biblioteca, Supervisión ni Historial.

## Dos lugares

| Lugar | Sentido de la URL | Acciones típicas |
|-----|----------|-------------------|
| Editor | Nueva o una red cargada | Dibujar, inspector, guardar, diálogo Abrir, duplicar, exportar el grafo abierto |
| Biblioteca | todas las redes | Búsqueda, etiquetas, definir como activa, importar/exportar varios archivos, borrar |

**Definir como activa** y **Borrar** pertenecen a la biblioteca (o a la selección rápida para activa). El diálogo Abrir del editor abre solo **una** red y no borra nada.

## Superficie del editor

Arriba la **cinta**: Nuevo, Guardar, Guardar como, Abrir, Duplicar, Exportar, Validar, Deshacer/Rehacer, Vista (ajustar, cuadrícula, ajuste, mini-mapa), A la biblioteca.

Centro: **Paleta** (izquierda), **lienzo**, **Inspector** (derecha). En pantallas estrechas paleta e inspector son cajones.

Nodos arrastrando desde la paleta. Las tarjetas se quedan compactas; los formularios están en el inspector. Selección múltiple con Mayús o lazo. Supr borra la selección. Deshacer: Ctrl+Z.

Mientras corre **exactamente esta** red: banner **Solo lectura** — primero detén en el encabezado.

## Tipos de nodo

| Nombre | Tipo | Tarea |
|-------------|-----|---------|
| Entrada de chat | `chat_input` | Texto inicial y entrada del usuario. **Como máximo una.** Salida **Mensaje**. |
| LLM | `llm` | Proveedor (Ollama, xAI, OpenAI, Claude, Gemini, compatible con OpenAI), modelo, credencial para la nube, temperatura, límite de tokens. Salida **LLM**. |
| Agente | `agent` | Prompt de sistema. Entradas Mensaje, LLM, Herramienta, Conocimiento. Salida Mensaje, opcional Transferencia. LLM, herramientas y conocimiento llegan **solo por aristas**, no como campos secretos. |
| Herramienta | `tool` | First-party: HTTP, búsqueda web, fecha/hora, calculadora — o **MCP**. Salida **Herramienta**. |
| Conocimiento | `knowledge` | Carpeta con archivos para la red. Salida **Conocimiento**, solo al puerto Conocimiento del agente. |
| Enrutador | `router` | Bifurca el mensaje según condiciones (primera línea / ramas con nombre) más salida por defecto. |
| Fin | `end` | Cierre. **Al menos uno.** |

## Conexiones

Solo puertos compatibles:

- Mensaje a Mensaje (Chat → Agente, Agente → Fin, Agente → Enrutador, ramas del enrutador → …)
- Salida LLM solo al **LLM** del agente — cada agente necesita **exactamente una** arista así
- Salida de herramienta al **Herramienta** del agente (varias permitidas)
- Salida de conocimiento solo al **Conocimiento** del agente
- Los ciclos están prohibidos (grafo dirigido sin bucles)

Un arrastre inválido se rechaza.

## Inspector

Ningún nodo elegido: nombre, descripción, etiquetas, estadísticas, lista de validación de la red **abierta**.

Nodo elegido:

- **LLM:** proveedor, modelo (lista del runtime), credencial para la nube, ping, avanzado temperatura / máx. tokens. Nube sin credencial es inválida.
- **Agente:** solo prompt de sistema y nombre visible.
- **Herramienta:** tipo. HTTP: método y URL, credencial opcional. Búsqueda web: credencial de tipo búsqueda web. MCP: servidor activado de Ajustes; por defecto todas las herramientas de ese servidor.
- **Conocimiento:** carpeta de origen (selector), topK, umbral de puntuación, **Reconstruir índice**. La carpeta debe estar **bajo la carpeta de datos**, no ser la raíz de la unidad ni el corpus de ayuda.
- **Entrada de chat:** marcador, texto inicial, interruptor «Entrada necesaria».
- **Enrutador:** ramas con nombre (nombre + condición) y predeterminada.

Los secretos **no** van en el texto del inspector ni en la exportación del grafo — solo la elección de una credencial.

## Validación

**Validar** en la cinta comprueba, entre otras cosas:

- Nombre no vacío
- como máximo una entrada de chat, al menos un fin
- cada agente: exactamente una arista LLM y un mensaje entrante
- LLM: modelo definido; nube: credencial
- Herramienta: tipo; MCP: servidor activo, ruta raíz si la receta la exige
- Conocimiento: ruta, sandbox, no corpus de ayuda
- sin aristas colgantes, sin ciclos, tipos de puerto compatibles

Válido/Inválido se ve como insignia. Las redes inválidas se pueden guardar, pero arrancan mal.

## Guardar, abrir, exportar

- **Guardar** (Ctrl+S): la primera vez diálogo de nombre, después actualización. La URL pasa a `/network/…`.
- **Guardar como:** documento nuevo, se convierte en el abierto.
- **Abrir:** una red guardada; búsqueda y orden. Acciones masivas y borrar solo en la biblioteca.
- **Duplicar:** solo con documento ya guardado; abre la copia.
- **Exportar:** descarga del grafo abierto. Incluye `credentialId`, no claves. La importación en la biblioteca descarta secretos adjuntos.

Salir sin guardar: diálogo Guardar / Descartar / Cancelar.

## Biblioteca

Lista con búsqueda (nombre, descripción, etiquetas), orden, filtros «solo válidas» / «solo activas». Selección múltiple.

Acciones: Nuevo (editor), Abrir, Duplicar, Renombrar, Poner etiquetas, **Definir como activa** (solo una red válida), Borrar, Importar, Exportar.

Borrar quita la entrada del espacio de trabajo, no tus archivos de conocimiento en disco, ni el corpus de ayuda ni las ejecuciones del historial. Una red **en ejecución** se omite. Borrar la red activa vacía la selección rápida.

Importar: archivos con colisión de nombre se renombran o se omiten. Las versiones de esquema no soportadas se rechazan.
