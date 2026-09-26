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

**Red (solo lectura):** el mismo grafo, colores de nodo según estado (inactivo, en espera, en curso, listo, error). Un clic en un nodo filtra registro/actividad y abre el detalle (rol, estado, espera LLM/herramienta/entrada/índice, último mensaje, tokens). Sin editar, sin segundo editor.

Si hay conocimiento en un agente, el inicio ya muestra la ejecución mientras se indexa: el nodo de conocimiento corre con motivo de espera **índice**, el registro nombra la lectura y los embeddings, y el encabezado y el panel muestran el mismo nombre. Un índice ya actual se omite y solo se anota como actual.

**Actividad:** nodos actuales, progreso «paso x de y», tokens entrada/salida, ventana de contexto opcional.

**Recursos del anfitrión:** CPU, RAM, GPU/VRAM **de este PC**, no solo de la app. Sin GPU local (típico en ejecuciones en la nube) aparece un aviso, no un error.

## Chat de red (supervisión)

Pestaña **Chat**: conversación del grafo en ejecución. Solo activa mientras corre. Sin orquestador el chat espera la primera línea y la pasa a la cadena. Con orquestador hablas solo con él. La ejecución espera solo ante una pregunta. Los textos de los agentes y las órdenes internas no se ven aquí.

Esto **no** es la burbuja de ayuda. Historial y herramientas son los de la red.

## Registro (supervisión)

Pestaña **Registro**: líneas con nivel (depuración, info, aviso, error), nodo, hora. Lo más nuevo arriba. Pausa detiene el seguimiento; «Ir a los más recientes» salta otra vez al final. Filtros: búsqueda, nivel mínimo, un nodo, solo errores. Exportar las líneas visibles.

Las cargas y los mensajes **enmascaran** secretos (por ejemplo `Bearer`, prefijos de clave). No los reenvíes sin filtrar.

## Historial

Cinta: Actualizar, borrar ejecuciones seleccionadas, exportar registros, depurar entradas antiguas según retención (véase Ajustes → Datos, predeterminado 90 días).

**Un filtro** lo controla todo: periodo (hoy, 7/30 días, desde–hasta), red, modelo, búsqueda (ID de ejecución, red, error). KPI, gráfico «ejecuciones por día», errores más frecuentes, pestañas Historial / Por modelo / Por red y la lista usan el mismo filtro.

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

Lado derecho o vista propia: meta, mini-grafo, pestañas **Registro**, **Pasos**, **Chat**. Pasos: nodo, rol, estado, error. Chat: transcripción, solo lectura. Exportar un registro suelto.

Borrar entradas del historial no cambia las redes guardadas.
