# Panel

La página de inicio. Resume configuración, red activa y últimas ejecuciones. **No** es supervisión en vivo ni archivo — hay páginas propias para eso.

## Configuración

La tarjeta **Configuración** aparece si falta algo para la primera ejecución, por ejemplo:

- Ollama no alcanzable → enlace **Verificar runtime**
- Perfil de ayuda sin proveedor o modelo → **Configurar ayuda**
- Aún no hay red → **Nueva red** o **Importar red**

Si el entorno está completo, la tarjeta se oculta. Los modelos opcionales que falten tras un setup silencioso sin descarga no son un segundo asistente: el ping de Runtime o el chat de ayuda muestran el error.

## Recursos del anfitrión

La misma tarjeta que en **Supervisión**: CPU, memoria y GPU/VRAM **de este PC**, no solo del proceso de la app. Los valores se actualizan en continuo, también sin ejecución activa.

## Estado

Indica si el servicio está **parado**, **iniciando**, **en ejecución** o **deteniendo**, más la red activa. Con red en marcha: enlace **Supervisión** y opcionalmente «en ejecución desde …». Sin selección rápida: aviso y enlace a la **Biblioteca**.

Iniciar y detener siguen en el **encabezado**, no en esta tarjeta.

## Red activa

Nombre, número de nodos/aristas, Válido/Inválido, última modificación. Acciones: **Editar** (editor), **Biblioteca**, **Nueva red**.

Inválido significa: la validación del editor falla (por ejemplo falta el modelo en un nodo LLM). Esas redes no deberías iniciarlas.

## Usados recientemente

Lista corta de redes guardadas por último uso. Un clic abre el editor. Vacío: aún no hay redes.

## Últimas ejecuciones

Las entradas más recientes del historial (éxito, error, cancelado, tiempo agotado, o aún en curso). Una entrada en curso lleva a **Supervisión**, las terminadas al **Historial**. Si el almacén de historial falla, aparece un aviso con enlace **Datos**.

## Últimos 7 días

Estadística breve: número de ejecuciones, con éxito, fallidas. Enlace **Historial** para filtros y gráficos. Es un resumen, no un segundo archivo.

## Entorno

- Ollama alcanzable o no, número aproximado de modelos
- Problemas de almacén (ajustes, ayuda, espacio de trabajo, historial)
- **Modo económico**, si la ayuda ha pasado al modelo de reserva

Enlaces: **Datos**, Runtime.

## Acceso rápido

**Nueva red**, **Importar** (biblioteca), **Runtime**. Las mismas acciones están en la navegación y en Ajustes.
