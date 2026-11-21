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

Centro: **Paleta** (izquierda), **lienzo**, **Inspector** (derecha). En el escritorio se pueden plegar. En pantallas estrechas son cajones. Una red vacía solo muestra la indicación de arrastrar el primer nodo de la paleta al lienzo. Las aristas son curvas, como en supervisión e historial.

Nodos arrastrando desde la paleta. Las tarjetas se quedan compactas; los formularios están en el inspector. Selección múltiple con Mayús o lazo. Supr borra la selección. Deshacer: Ctrl+Z.

Mientras corre **exactamente esta** red: banner **Solo lectura** — primero detén en el encabezado.

## Tipos de nodo

| Nombre | Tipo | Tarea |
|-------------|-----|---------|
| Chat | `chat_input` | Conversación de la ejecución. **Como máximo uno.** Salida **Mensaje**. Con orquestador el chat sigue abierto para preguntas. |
| Orquestador | `orchestrator` | Voz del chat de la ejecución. Entradas **Mensaje**, **LLM** y **Herramienta**. Una salida **Canal** por agente. **Mensaje** solo hacia **Fin** (o enrutador). **Como máximo uno.** |
| LLM | `llm` | Proveedor (Ollama, xAI, OpenAI, Claude, Gemini), modelo, credencial para la nube, temperatura, límite de tokens. Salida **LLM**. |
| Agente | `agent` | Prompt de sistema. Entradas Mensaje, LLM, Herramienta, Conocimiento y **Canal** opcional. Salidas Mensaje y Transferencia. El canal viene solo del orquestador. Sin canal el agente corre una vez por el mensaje. |
| Herramienta | `tool` | First-party: HTTP, búsqueda web, fecha/hora, calculadora, acceso a archivos. Salida **Herramienta**. |
| MCP | `mcp` | Un servidor creado y **activado** en **Ajustes**. Salida **Herramienta**, como un nodo de herramienta. |
| Conocimiento | `knowledge` | Carpeta con archivos para la red. Salida **Conocimiento**, solo al puerto Conocimiento del agente. |
| Enrutador | `router` | Envía el mensaje a una sola salida. Las ramas se comprueban en orden: contiene, empieza por, primera línea, expresión regular. El estándar recoge el resto. Tras el orquestador, las salidas solo van a fines. |
| Fin | `end` | Cierre. **Al menos uno.** |

## Conexiones

Solo puertos compatibles:

- Mensaje a Mensaje (Chat → Agente o Chat → Orquestador, Agente → Fin, Agente → Enrutador, ramas del enrutador → …). El orquestador envía Mensaje solo a Fin o a un enrutador.
- Canal a Canal (Orquestador → Agente). Un puerto por agente. La respuesta vuelve dentro de la ejecución, sin una segunda arista.
- Salida LLM al **LLM** del agente o del orquestador — cada agente y el orquestador necesitan **exactamente una** arista así
- Salida de herramienta al **Herramienta** del agente o del orquestador (varias permitidas). Una herramienta puede ir a ambos.
- Salida de conocimiento solo al **Conocimiento** del agente
- Los ciclos están prohibidos (grafo dirigido sin bucles)

Un arrastre inválido se rechaza.

## Inspector

Ningún nodo elegido: nombre, descripción, etiquetas, estadísticas, lista de validación de la red **abierta**. Las etiquetas son chips; Intro, coma o más confirma una etiqueta, la cruz la quita. La biblioteca filtra por las mismas etiquetas.

Nodo elegido:

- **LLM:** proveedor, modelo (lista del runtime), credencial para la nube, longitud de contexto según el modelo (deslizador local, lista en la nube), hilos de CPU por nodo (por defecto: núcleos físicos), offload GPU un paso por capa (por defecto: todas las capas, Auto si falla la carga), memoria GPU estimada según contexto y offload (últimas N capas en la GPU; atención completa sobre todo el contexto, capas de ventana deslizante solo su ventana; aviso si no cabe en la tarjeta), ping, avanzado temperatura (de 0 a 2, con Anthropic de 0 a 1) y máx. tokens (un número entero de 64 a 262144, menor que el contexto). Nube sin credencial es inválida. Los campos numéricos aceptan al instante un valor válido; un valor fuera del rango se ajusta al salir del campo. Una red importada con valores no válidos muestra un error de validación y no se inicia.
- **Agente:** prompt de sistema y nombre visible. Si el agente está en un canal, el inspector explica que los encargos vienen del orquestador. Puede pensar internamente antes de escribir o llamar a una herramienta; el pensamiento no aparece en el chat. **Llamadas a herramientas por encargo** limita sus llamadas (vacío: 100); después responde con lo que tiene.
- **Herramienta:** tipo. HTTP: método y URL, credencial opcional. La credencial solo se envía a la dirección de esa URL (esquema, host, puerto); con credencial la URL es obligatoria. Búsqueda web: credencial de tipo búsqueda web. Acceso a archivos: carpeta raíz, no la raíz de la unidad; el agente solo trabaja debajo, y escribir y borrar son interruptores. **Buscar** encuentra nombres de archivo con un patrón (`*.css`) o, con `text`, un texto dentro de un archivo o de los archivos de una carpeta, con ruta, número de línea y línea; la búsqueda de texto omite `node_modules` y `.git`. Terminal (restringido): un programa permitido con sus argumentos, sin shell. Lo que los modelos añaden por costumbre y aquí no cambia nada, la herramienta lo quita y se lo dice al modelo: `cd` a la carpeta de trabajo, `2>&1` y un `| head -N` o `| tail -N` al final (la salida se recorta entonces a esas líneas). Otras tuberías, `&&`, `;` y redirecciones siguen rechazándose.
- **MCP:** servidor activo en **Ajustes → Servidores MCP**. Por defecto todas las herramientas; tras una prueba puedes elegir un subconjunto. Las credenciales van en Ajustes. La carpeta raíz de sistema de archivos y Excel está en el nodo; Git conserva la carpeta en Ajustes.
- **Conocimiento:** carpeta de origen (selector), proveedor de embeddings (Ollama, OpenAI o Gemini) y modelo de embeddings, topK (de 1 a 20, vacío: 4), umbral de puntuación (de 0 a 1, vacío: 0), **Reconstruir índice**. La carpeta puede estar en cualquier sitio salvo una raíz de unidad o de sistema y el corpus de ayuda. Se indexan Markdown, texto, PDF, Word (.docx), Excel (.xlsx), HTML, JSON, CSV y código. Las imágenes y los .doc/.xls antiguos se omiten. Los embeddings en la nube necesitan credencial. El índice pertenece a esta red, no a la ayuda.
- **Chat:** marcador, texto inicial, interruptor «Entrada necesaria».
- **Orquestador:** prompt de sistema. El modelo elige pensar, una pregunta, un encargo a un agente por su canal, una respuesta o el cierre. Pensar no aparece en el chat y no cuenta contra el límite de pasos; solo cuentan los encargos a agentes. Los agentes son los canales, no una segunda lista. Llama él mismo las herramientas conectadas: leer archivos en cualquier momento, como mucho 15 llamadas por decisión (ajustable) y diez en total antes del primer encargo. Si quiere seguir leyendo, recibe para ello la siguiente decisión; volver a leer solo lo ya leído cuenta como falta de avance. Cambiar archivos, el terminal y las demás herramientas solo después de que falle un agente o durante una toma de control. Su prompt dice qué puede alcanzar: qué herramientas están conectadas, para qué sirven y si están abiertas ahora o solo después de que falle un agente. Sin herramientas propias dice que no puede leer archivos y que encarga las comprobaciones a un agente. La lista de agentes nombra las herramientas de cada uno. Las reglas y los detalles solo aparecen para las herramientas abiertas en ese momento. Con herramientas también puede decidir mediante llamadas (call_agent, ask_user, reply, finish). La misma llamada se ejecuta solo una vez por paso; una herramienta que falla tres veces con el mismo error, o cuya llamada se repite dos veces, se retira en ese paso. Solo una pregunta espera al usuario.
  - **Intentos fallidos por agente** (vacío: 2): cuántas veces seguidas un agente puede fallar o terminar un encargo de archivos sin cambios. Después el orquestador hace esa tarea él mismo.
  - **Encargos a agentes por ejecución** (vacío: 50): cuenta cada encargo, también las rondas de revisión y las comprobaciones. Al llegar al límite, el orquestador resume en el chat lo que está hecho y lo que queda pendiente; después la ejecución termina con un aviso del límite.
  - **Llamadas a herramientas por decisión** (vacío: 50) y **Llamadas al modelo por ejecución** (vacío: 1000, orquestador y agentes juntos).
  - **Lecturas por decisión** (vacío: 15): cuántos archivos lee el orquestador en una decisión mientras solo puede leer. Si quiere seguir leyendo, recibe para ello la siguiente decisión. Antes del primer encargo rigen como mucho diez en total.
  - Si el orquestador toma varias decisiones seguidas sin avanzar (sin encargo a un agente, sin resultado nuevo de herramienta, sin mensaje nuevo), la ejecución se lo recuerda tras cuatro. Tras ocho recibe una última ronda sin herramientas para un resumen en el chat; después la ejecución termina como atascada.
- **Enrutador:** ramas con nombre (nombre + condición) y predeterminada.

Los secretos **no** van en el texto del inspector ni en la exportación del grafo — solo la elección de una credencial.

## Validación

**Validar** en la cinta comprueba, entre otras cosas:

- Nombre no vacío
- como máximo un chat, como máximo un orquestador, al menos un fin
- las carpetas del acceso a archivos, del terminal y de ZIP existen; si falta una, la ejecución no arranca. Si una carpeta desaparece durante la ejecución, esa herramienta se desactiva
- sin orquestador, la cadena lleva desde su inicio (chat o primer agente) hasta un fin; con orquestador, este tiene un canal hacia al menos un agente
- cada agente: exactamente una arista LLM. Sin orquestador, un mensaje entrante. Con orquestador, exactamente un canal y ninguna cadena de mensajes en el mismo agente
- LLM: modelo definido; nube: credencial
- Herramienta: tipo; MCP: servidor activo, ruta raíz si la receta la exige; acceso a archivos: una carpeta que no sea la raíz de la unidad
- Conocimiento: ruta puesta, no una raíz, no el corpus de ayuda, credencial de embeddings si el proveedor la exige
- sin aristas colgantes, sin ciclos, tipos de puerto compatibles

Válido/Inválido se ve como insignia. Las redes inválidas se pueden guardar, pero arrancan mal.

## Guardar, abrir, exportar

- **Guardar** (Ctrl+S): la primera vez diálogo de nombre, después actualización. La URL pasa a `/network/…`.
- **Guardar como:** documento nuevo, se convierte en el abierto.
- **Abrir:** una red guardada; búsqueda y orden. Acciones masivas y borrar solo en la biblioteca.
- **Duplicar:** solo con documento ya guardado; abre la copia.
- **Exportar:** diálogo y luego JSON del grafo abierto (`schemaVersion` 1). Incluye `credentialId`, no claves.
- **Importar:** diálogo para un archivo JSON. Se crea una red nueva. Un nombre ya usado se cambia, o se omite el archivo.

Salir sin guardar: diálogo Guardar / Descartar / Cancelar.

## Biblioteca

Lista con búsqueda (nombre, descripción, etiquetas), orden, filtros «solo válidas» / «solo activas». Selección múltiple.

Acciones: Nuevo (editor), Abrir, Duplicar, Renombrar, Poner etiquetas, **Definir como activa** (solo una red válida), Borrar, Importar, Exportar. Poner etiquetas carga las etiquetas existentes de la selección como chips.

Borrar quita la entrada del espacio de trabajo, no tus archivos de conocimiento en disco, ni el corpus de ayuda ni las ejecuciones del historial. Una red **en ejecución** se omite. Borrar la red activa vacía la selección rápida.

Importar: diálogo con vista previa. Mismo nombre: renombrar u omitir. Otra schemaVersion se rechaza. Los secretos se descartan.
