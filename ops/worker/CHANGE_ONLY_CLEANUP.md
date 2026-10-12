# Retirada cerrada de las pruebas del modelo anterior

Estado: productor físico implementado y probado; **no instalado ni aplicado**.
El preflight real devuelve READY_FOR_MAINTENANCE, no RELEASED.
La operación no se expone al móvil/AgentRuns ni recibe targets o comandos.

## Autoridad y alcance exactos

Autorización del 12 de octubre: retirar todas las pruebas independientes,
conservar únicamente el Apache real y WS21. Confirmación adicional: la rama
`ax42-beautips-wip-preservation-2ac2a5fd` ya no tiene valor y debe retirarse.
El respaldo técnico privado no crea compatibilidad ni historia en el producto.

El manifiesto fijado por SHA-256 identifica 25 roots: uno protegido y 24 de
pruebas. El conjunto incluye 25 refs por SHA esperado (también la rama WIP y
la original de WS4), tres contenedores de WS4, una red y seis volúmenes.
Nunca se borra un mirror, main, tags, imágenes compartidas, releases Codex,
servicios humanos, repositorios externos ni un directorio padre completo.

La correlación read-only ya comprobó las cinco DB App existentes: PROD,
DEV, preview y dos controles antiguos. Los controles ligan las sesiones
`6375c738…` y `c20f3cde…` a WorkSessions CLOSED. Los fixtures de
MariaDB/PostgreSQL/Tomcat y sus commits están documentados en el programa
versionado. Los journals RELEASED ligan `dd40ea77…` a `310b7ac7…` y
`95232b9c…` a `b65ddd19…`; el otro workspace M2 está limpio,
sin registro vigente ni dueño App. No se seleccionan nuevos UUID por ausencia
o antigüedad: un root/record/ref adicional o diferente bloquea la operación.

Los artefactos sin root identificados como sintéticos (fase 5 y adjuntos
96061), el preview EXPIRED de WS4, caches, adjuntos, admissions y journals
dependientes se retiran por sus rutas/identidades fijas. Los ocho registros
worker del Apache y sus 21 validaciones se conservan; se archivan y retiran
60 ejecuciones terminales de pruebas del índice durable, sin tocar el catálogo
ni el árbol Codex. Los backups de programas externos no se borran.

## Instalación y precondiciones

El installer Platform normal instala/verifica el productor, lector de plan,
manifiesto y schema versionado root-owned. Sólo prepara directorios de backup
si están ausentes; un propietario, enlace o permiso ajeno detiene el preflight.
No ejecuta cleanup ni añade permisos sudoers al worker.

Después de integrar el conjunto, el despliegue Platform debe incluir la
verificación v4-only independiente de WS19. El productor exige los bytes
exactos de esa función instalada, además de autoridad root del script.

La aplicación de la retirada requiere mantenimiento coordinado:

- App `atenea-backend-prod` parada; el productor lo lee por el SSH de operador
  ya existente, sin introducir credenciales ni pedir root SSH.
- AX42: worker, preview, servicio de adjuntos y release-control inactivos.
  El productor **no** los detiene ni reinicia por su cuenta.
- Cero ejecuciones/validaciones/operaciones no terminales; configuración,
  refs, inventario worker, registro y recursos iguales al estado revisado.
- Script y padres root-owned/protegidos; lock exclusivo de esta operación.
  No hay flags de test, paths, hosts, versiones ni comandos del llamante.

El plan read-only no exige parar servicios. `--apply` sí. `--verify` se usa
dentro de la misma ventana de mantenimiento antes de devolver el runtime a
servicio. No sustituir estas precondiciones con ficheros fabricados.

## Secuencia durable

1. Congelar plan, recursos protegidos, estado e identidades en el journal fijo.
2. Respaldar archivos completos (incluido trabajo sin commit), registros,
   historial worker y configuración. Tars root-private verificados miembro a
   miembro: contenido SHA-256, estructura, permisos y ownership; sin seguir
   enlaces ni ejecutar contenido. Crear/verificar bundles de los mirrors.
3. Parar solamente los tres contenedores fijados de WS4. Rechazar mounts,
   identidades o consumidores de volumen inesperados. Con ellos quietos,
   respaldar y verificar los seis volúmenes antes de la primera eliminación.
4. Retirar esos contenedores, red y volúmenes por ID exacto, sin force/prune.
   Desregistrar el antiguo perfil Beautips (false/false/workspaces vacíos) por
   transición de bytes cerrada; no cambiar sus restantes campos.
5. Desregistrar worktrees mediante Git, sólo tras comprobar que todos sus
   bytes siguen coincidiendo con el respaldo; borrar las refs con compare-and-
   delete del SHA esperado. No hay fetch, reset, gc ni force push.
6. Mover el resto de archivos retirados a cuarentena privada fuera del producto,
   preservando el backup verificable. Contraer el índice worker fijo manteniendo
   íntegros los registros del Apache y las validaciones.
7. Verificar ausencia de los targets y conservación del workspace/refs Apache,
   configs, enlaces Codex y contenedores ajenos. Sólo después persistir
   RELEASED y emitir el recibo versionado que consume el purgador DB App.

Destino fijo: `/srv/atenea/backups/ax42/change-only-20261012/`.
Recibo: `/etc/atenea-release-v1/change-only-resources.json`, root/0600.
No copiar un plan como recibo. El operador transferirá únicamente el recibo
auténtico al VPS por el canal autenticado y verificará sus bytes/autoridad.

Cada efecto tiene intención durable previa y acuse posterior. Un retry usa la
misma operación; ausencia Docker, tar completo sin acuse, refs ya retiradas,
quarantines e índice ya contraído se reconcilian, no se repiten ciegamente.
Backup corrupto, ownership drift o postcondición fallida detienen el proceso
sin emitir recibo. No reparar symlinks, permisos o journals manualmente.

## Validación y continuación

17 tests focales del productor con archivos/Git reales efímeros, sin Docker,
SSH ni recursos PROD; 12 del preflight; installer focal, bash -n,
schemas Draft 2020-12 y diff-check. Cubren la rama WIP autorizada, rechazo
de variantes, código cambiado después de backup, backups fallidos/corruptos,
consumidor Docker ajeno, replay, acuses perdidos y conservación del Apache.

Antes del rollout del conjunto queda retirar los clientes/flags/tablas App
legacy que aún no forman parte del modelo único. Después: backup PostgreSQL16
y mantenimiento, retirada física, purga DB exacta, V94 y contracción de tablas,
arranque/smoke, APK y aceptación móvil. Esta unidad no despliega, aplica Flyway,
apaga servicios, ejecuta la retirada real ni publica APK.
