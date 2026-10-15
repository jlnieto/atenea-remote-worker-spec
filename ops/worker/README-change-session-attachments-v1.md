# Imágenes de un Cambio

El broker privado añade GET `/v1/capabilities/change-session-attachment`, contrato
`change-session-attachment/v1`. El PUT v1 conserva rutas deterministas por UUID
remoto y los headers privados derivados por App. No admite rutas ni comandos.

App es autoridad de la vinculación WorkSession → DevelopmentChange. El broker
verifica además el registro worker-owned 0600 del Cambio existente bajo el root
fijo, proyecto Atenea/1, worker ax42-01, branch e identidad exactas y directorios
no simbólicos. En el primer PUT retiene atómicamente `owner-v1.json`: ese UUID
remoto no puede cambiar de propietario. Comprueba los sidecars ya retenidos;
rechaza cruces con otro Cambio o almacenamiento legado. No crea workspaces.

El scope sigue siendo REAL_SESSION, con los mismos límites, hashes, sidecars y
referencias de imagen de project-codex-v4. El runner ya reconstruye únicamente
las imágenes enlazadas al turno y comprueba la identidad change-owned. Ni el
inventario de adjuntos ni los ficheros privados de otros cambios se exponen al
sandbox. Las lecturas históricas no requieren recrear el workspace.

Desplegar desde el SHA integrado limpio con el installer existente
`install-worksession-attachment-v1.sh apply`, conservando token, root y regla
tailnet exacta; ejecutar `verify` y health/capabilities autenticados. El installer
del worker principal no sustituye al del broker. Esta operación no activa Codex,
crea AgentRuns ni altera los workspaces de los cambios.
