# Supervisión e historial

**Supervisión** = ahora, una ejecución. **Historial** = archivo y estadísticas. El historial **no** es un segundo panel ni un registro en vivo. Iniciar y detener siguen en el **encabezado**.

## En vivo frente a archivo

| | Supervisión | Historial |
|---|------------|----------|
| Cuándo | el servicio inicia, corre o se detiene | tras el fin de la ejecución (y enlace mientras aún corre) |
| Grafo | mini-grafo, solo lectura, estado de nodos | instantánea guardada, sin actualización en vivo |
| Registro | flujo, lo más nuevo arriba, se puede pausar | líneas fijas, filtrables |
| Chat | chat de la ejecución, solo mientras corre | transcripción guardada, no se continúa |

Una entrada de historial aún en curso es solo un salto a Supervisión («Ver en vivo»).

## Supervisión sin ejecución

Sin ejecución activa la página muestra la **última ejecución guardada** para leerla (grafo, actividad, registro, chat). Un aviso dice que nada está en vivo. La página queda del todo vacía solo si aún no hay ninguna ejecución guardada: **Sin ejecución**, más la red activa o el aviso de que la selección rápida está vacía. Desconectado / error / iniciando / deteniendo tienen textos propios. Mientras se indexa conocimiento, el aviso de inicio pasa al nombre de ese nodo. Los últimos valores pueden quedar atenuados hasta que haya conexión.

## Durante una ejecución

Cabecera: ID de ejecución, hora de inicio, duración, paso aproximado, LLM activos (local frente a nube).

**Red (solo lectura):** el mismo grafo, colores de nodo según estado (inactivo, en espera, en curso, listo, error). Un clic en un nodo filtra registro/actividad y abre el detalle (rol, estado, espera LLM/herramienta/entrada/índice/pensando, último mensaje, tokens). Sin editar, sin segundo editor.

Si hay conocimiento en un agente, el inicio ya muestra la ejecución mientras se indexa: el nodo de conocimiento corre con motivo de espera **índice**, el registro nombra la lectura y los embeddings, y el encabezado y el panel muestran el mismo nombre. Un índice ya actual se omite y solo se anota como actual.

**Actividad:** nodos actuales, progreso «paso x de y», tokens entrada/salida, ventana de contexto opcional.

Chat y registro están encima de la red y la actividad. Las tres tarjetas mantienen su altura al agrandar la ventana; se arrastra el borde para cambiar el tamaño. Los tamaños se conservan al cerrar la aplicación.

**Recursos del anfitrión:** CPU, RAM, GPU/VRAM **de este PC**, no solo de la app. Sin GPU local (típico en ejecuciones en la nube) aparece un aviso, no un error.

## Chat de red (supervisión)

Pestaña **Chat** (al iniciar una ejecución, si el grafo tiene entrada de chat): conversación del grafo en ejecución. Solo activa mientras corre. Sin orquestador el chat espera la primera línea y la pasa a la cadena. Con orquestador hablas solo con él. La ejecución espera solo ante una pregunta. Los textos de los agentes y las órdenes internas no se ven aquí. Una pregunta aparece en la campana y en la cabecera; el icono de la barra de tareas parpadea si la ventana está en segundo plano. **Detener la generación** corta la respuesta en curso. Con orquestador la ejecución sigue abierta y espera tu siguiente mensaje; en una cadena sin orquestador termina como cancelada.

Esto **no** es la burbuja de ayuda. Historial y herramientas son los de la red.

## Registro (supervisión)

Pestaña **Registro**: una línea por evento como frase, lo más nuevo arriba. Delante: hora, icono (decisión, agente, herramienta, modelo, límite) y estado (✓ correcto, ✗ falló, ⚠ aviso); a la derecha la duración. Ejemplos: «Senior: lee src/App.tsx · 41 líneas», «Senior: ejecuta: npm run build · código de salida 1: …», «Jefe: llama a Senior: corregir RTL». Pausa detiene el seguimiento; «Ir a los más recientes» salta otra vez al final.

**Vista:**

- **Importante** (por defecto): decisiones del orquestador, encargos, resultados, límites, avisos y errores.
- **Todo**: además cada llamada a herramientas y modelos.
- **Depuración**: además líneas de depuración, por ejemplo inicios de modelo.

**Grupos:** Cada encargo de un agente es un grupo. La cabecera nombra agente, encargo y resultado (llamadas a herramientas, archivos modificados, duración); la flecha muestra las líneas de debajo. Un encargo en curso está expandido.

**Filtros:** La búsqueda encuentra el texto mostrado, el encargo, el resultado, la ruta y el comando. El filtro de nodo muestra también las llamadas a herramientas y modelos de ese agente. Además «solo errores».

**Detalle:** clic en una línea. Las herramientas muestran ruta o comando, resultado, error y la indicación para el modelo; los agentes, encargo y resultado; las llamadas al modelo, tokens, duración, respuesta y razonamiento. Los datos sin procesar (JSON) se pueden desplegar.

**Resumen:** Al final de una ejecución, una tarjeta arriba muestra resultado, duración, llamadas a agentes por agente, llamadas al modelo y tokens, llamadas a herramientas, archivos modificados y límites alcanzados.

**Exportar:** «Exportar como texto» guarda las líneas mostradas como Markdown, «JSON» como JSON Lines. El contenido de archivos se recorta a 2 KB en el registro, las respuestas del modelo a 8 KB.

Las cargas y los mensajes **enmascaran** secretos (por ejemplo `Bearer`, prefijos de clave). No los reenvíes sin filtrar.

## Historial

Cinta: Actualizar, borrar ejecuciones seleccionadas, exportar registros, depurar entradas antiguas según retención (véase Ajustes → Datos, predeterminado 90 días; con «Ilimitado» no aparece el botón).

**Un filtro** lo controla todo: periodo (hoy, 7/30 días, desde–hasta), red, modelo, búsqueda (ID de ejecución, red, error). KPI, gráfico «ejecuciones por día», errores más frecuentes, pestañas Historial / Por modelo / Por red y la lista usan el mismo filtro.

El gráfico y la lista de errores, y la lista de ejecuciones y el detalle, se redimensionan arrastrando el borde, igual que en Supervisión. Los tamaños se conservan al cerrar la app.

## Resultados de una ejecución

| Resultado | Significado |
|----------|-----------|
| En ejecución | aún activa — en el historial solo como enlace |
| Éxito | terminó con normalidad |
| Error | falló un paso o el servicio |
| Cancelado | Detener en el encabezado, ventana cerrada, o fin de la app (también tras un cierre brusco, en el siguiente arranque) |
| Tiempo agotado | se superó el tiempo |

**Cancelado no es error.** Tiempos agotados y cancelaciones se cuentan aparte en los KPI (pie de «Error»).

## Detalle de la ejecución

Lado derecho o vista propia: meta, mini-grafo, pestañas **Registro**, **Pasos**, **Chat**. El registro se ve como en la supervisión: vistas, grupos, resumen, exportar como texto. Las ejecuciones antiguas tienen menos datos (sin encargo, sin llamante). Pasos: nodo, rol, estado, error. Chat: transcripción, solo lectura. Exportar un registro suelto.

Borrar entradas del historial no cambia las redes guardadas.
