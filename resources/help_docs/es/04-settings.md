# Ajustes

Engranaje en el encabezado. Secciones a la izquierda: Apariencia, Credenciales, Runtime, Chat de ayuda, Servidores MCP, Datos, Acerca de. Campos sin guardar al cambiar: diálogo Quedarse / Descartar.

## Apariencia

Claro, oscuro o sistema — vale para toda la app, incluido el encabezado. **Idioma** es un desplegable con bandera: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. El nombre entre paréntesis es la traducción en el idioma de la interfaz actual.

Interruptor **Botón de ayuda**: muestra u oculta la burbuja abajo a la derecha. La **configuración** del chatbot sigue en **Chat de ayuda**, aunque la burbuja esté oculta.

## Credenciales

Secretos con nombre para modelos en la nube, búsqueda web y algunas recetas MCP. Crear: nombre, tipo, secreto **una vez**. Después solo la **máscara**. Editar puede sustituir el secreto (vacío = sin cambios).

Tipos entre otros: xAI, compatible con OpenAI, búsqueda web, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, token.

**Borrar** está bloqueado mientras el perfil de ayuda, una red (LLM/herramienta) o un servidor MCP usen la credencial. Primero quita la asignación.

## Runtime

**URL base de Ollama** (suele ser la dirección local de Ollama) y opcionalmente **URL base compatible con OpenAI**. **Comprobar conexión** y la **lista de modelos** pasan por la app, no por el navegador.

Sin Ollama alcanzable, los nodos LLM locales y la ayuda predeterminada se quedan parados. Los modelos los instalas con Ollama o en el setup; la app **no** hace pull en silencio en tiempo de ejecución.

## Chat de ayuda

Único sitio para el widget de ayuda. Incompleto sin proveedor y modelo de chat.

- Proveedor y modelo de chat (predeterminado Ollama / `llama3.2:1b`)
- credencial de nube opcional
- **Proveedor y modelo de embeddings** (predeterminado Ollama / `nomic-embed-text`) — **no** es el modelo de chat
- modelo económico opcional (reserva, predeterminado el mismo chat pequeño)
- búsqueda web sí/no más credencial de búsqueda; sin credencial el chat sigue configurado y la búsqueda apagada
- comprobar conexión, borrar historial, **reconstruir índice**, volver a mostrar el onboarding

Tras cambiar el modelo de embeddings o añadir archivos al corpus de ayuda: **reconstruir índice**. El corpus es la carpeta de documentos de ayuda en la carpeta de datos, no el conocimiento de la red.

La ayuda **no** usa servidores MCP ni el conocimiento de los grafos.

## Servidores MCP

Plantillas (**recetas**) para herramientas externas: GitHub, sistema de archivos, Git, Playwright, Postgres, Slack, Notion, formatos Office y otras. Las recetas no son programas incluidos. Muchas necesitan Node/`npx`, Docker o `uvx` en el PC más una credencial.

Predeterminado: servidor **inactivo**. La app no arranca procesos MCP al abrir, sino cuando una ejecución necesita un nodo de herramienta MCP conectado.

Crear desde una receta (credencial, ruta raíz opcional) o como **servidor propio** (comando, argumentos o URL). Usa comandos desconocidos solo si confías en ellos. La sonda comprueba si responde; «Falta el runtime» si no hay Node/Docker/`uvx`.

Office agrupa PDF y formatos Office; activa los presets sueltos solo si de verdad los necesitas.

Borrar quita la configuración del servidor, no Ollama ni las credenciales.

## Datos

Muestra la **carpeta de datos** y el estado de los almacenes: Ajustes, Ayuda, Espacio de trabajo, Historial — sin vista SQL y sin secretos.

**Cambiar** carpeta solo si ninguna red inicia, corre o se detiene. Las raíces de unidad o de sistema no valen. Opcional copiar el contenido a la carpeta nueva; la antigua se queda.

**Portátil** o una carpeta impuesta desde fuera: ruta **de solo lectura**.

**Retención del historial:** 30 / 90 / 365 días o ilimitado (predeterminado 90). La página de historial puede depurar entradas antiguas acorde.

## Acerca de

Versión de UI y API, estado aproximado de Ollama, si los almacenes responden. Sin secretos ni rutas internas con nombre de usuario en una superficie que compartirías.
