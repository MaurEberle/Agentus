# Arquitecto

El **Arquitecto** es un agente de chat que diseña una red contigo: agentes, prompts, modelos y herramientas. Si lo pides, crea la red o cambia una existente. Conoce los tipos de nodo, campos y herramientas de la versión instalada. El chat de ayuda, en cambio, explica la aplicación; ambos están separados.

## Iniciar

El arquitecto nunca arranca solo. En el módulo **Arquitecto** eliges proveedor, credencial (en la nube) y modelo de chat, y pulsas **Iniciar sesión**.

- **Modelos de Ollama:** necesitan llamadas a herramientas y al menos 4B parámetros; los menores o sin herramientas están bloqueados. Hasta 14B aparece un aviso.
- **GPU:** solo arranca si el modelo (y un modelo de embeddings local para los ejemplos) cabe en la memoria de vídeo libre. Si memoria de vídeo y RAM juntas bastan, la aplicación ofrece **Iniciar de todos modos (lento)**.
- **Si una red está en ejecución**, la aplicación avisa claramente antes de arrancar.
- **Chat de ayuda:** si arquitecto y chat de ayuda funcionan ambos en local, el chat de ayuda se pausa durante la sesión. El arquitecto tiene prioridad.
- **Terminar sesión** detiene una respuesta en curso y descarga el modelo de Ollama. Tras **15 minutos** sin entrada la sesión termina sola; chat, ficha y borrador se conservan, continuar la reinicia.

## Ficha y borrador

- **Ficha:** objetivo, entrada, resultado, fuentes, local o nube, herramientas, límites, cada campo como entrada desplegable. El arquitecto la rellena en la conversación; con el lápiz cambias un campo (Ctrl+Intro guarda). Debajo, **Prompts** muestra los prompts de los agentes del borrador, con formato para leer.
- **Borrador:** a la derecha como grafo. La insignia **válido** o **N errores** muestra la comprobación; al pulsarla se listan errores y avisos. El arquitecto corrige los errores; tras tres intentos fallidos te pregunta.
- **Guías:** lineal, orquestador, chat de conocimiento, triaje con router. El arquitecto lee la adecuada antes de diseñar.

## Cargar redes

**Cargar red …** elige una red guardada, **para cambiarla** o **como plantilla** (al final surge una red nueva). También funciona en un chat vacío, antes de iniciar la sesión. Si el arquitecto lo pide, aparece una tarjeta sobre la entrada; no se carga nada antes de tu clic.

Al cambiar, la vista previa marca en verde los nodos nuevos y en amarillo los cambiados; **N cambios** bajo el nombre de la red los enumera.

**Modelos en la nube:** ven la estructura y los prompts de una red solo cuando la cargas expresamente. Las rutas de carpetas quedan ocultas salvo que lo permitas en **Ajustes → Arquitecto**.

## Terminar

Cuando el borrador es válido, el arquitecto propone terminar, o pulsas **Terminar …**. El diálogo de cierre muestra resumen, estructura, en cambios las diferencias con la versión guardada y piezas de riesgo (terminal sin restricciones, acceso a archivos con borrado, HTTP con credencial).

Opciones: **Marcar como activa**, **Añadir prompts a la biblioteca** (desactivado por defecto), **Abrir después en el editor**. No se guarda nada antes de **Crear** o **Aplicar cambios**, y se guarda como versión nueva con origen «Arquitecto».

- **Si la red está en ejecución**, no se aplica nada.
- **Si la red se guardó en otro sitio desde que se cargó**, el diálogo lo indica: **Volver a cargar** descarta el borrador, **Aplicar de todos modos** lo pone encima como versión nueva.
- **Deshacer última aplicación** recupera la versión anterior a la aplicación, como versión nueva.

## Investigación

- **Búsqueda web:** ajustes propios en **Ajustes → Arquitecto**, separados del chat de ayuda; desactivada por defecto.
- **Hugging Face:** el arquitecto busca modelos GGUF y lee cuantizaciones, tamaños y licencia. Los descargas tú en **Modelos → Hub**.
- **Límites:** llamadas a herramientas por respuesta, búsquedas web y consultas al Hub por sesión. 0 desactiva la búsqueda web o la del Hub.

## Ejemplos

El arquitecto busca redes de ejemplo que encajen con la ficha. Los ejemplos incluidos llegarán con una actualización posterior. **Usar mis redes como ejemplos** (Ajustes → Arquitecto) solo toma redes válidas; los modelos en la nube no ven prompts. Sin modelo de embeddings, el arquitecto busca por palabras clave.

## Sesiones

A la izquierda están las sesiones con chat, ficha y borrador. **Nueva** abre un chat vacío: si hay una sesión en marcha, la nueva arranca enseguida con el mismo modelo, que sigue cargado; si no, eliges un modelo e inicias. **Markdown** exporta una sesión, **Borrar** la elimina; las redes creadas se conservan.
