# Release control v1: bootstrap único y publicaciones cerradas

Este ejecutor vive fuera de App. Reiniciar App no mata el trabajo ni pierde
su resultado. AX42 no recibe una clave SSH del VPS, la firma Android ni
credenciales PostgreSQL PROD. Sólo el VPS inicia solicitudes hacia AX42.
Nada de este documento se ejecuta por implementar o integrar el código.

## Autoridades fijas

| Destino | Repositorio/artefacto | Único efecto autorizado |
| --- | --- | --- |
| APP_PROD | `jlnieto/atenea`, `image.tar` | Recrear sólo `atenea-backend-prod` |
| AX42_PLATFORM | `jlnieto/atenea-remote-worker-spec`, `platform.tar` | Installer worker `apply` y `verify` |
| ANDROID_STABLE | `jlnieto/atenea`, `app-unsigned.apk` | Firmar con la identidad instalada y actualizar el canal interno |

Las solicitudes son PLAN, INSPECT, EXECUTE y OBSERVE_APP. Ninguna acepta rutas, comandos,
hosts, versiones, claves de firma, servicios o enlaces. Los schemas cerrados
están en `runtime-contract/release-control-v1.*.schema.json`.

`OBSERVE_APP` acepta únicamente `{"operation":"OBSERVE_APP"}` en el VPS.
Es una lectura de identidad de la imagen realmente ejecutada, health local
y recibo root-owned de una publicación APP_PROD terminada correctamente.
Devuelve `atenea-app-observation/v1`, sin configuración, rutas ni secretos.
Comprueba el hash del plan y vincula recibo, operación, commit e imagen;
rechaza publicaciones ambiguas/en curso y cambios de runtime durante la lectura.
No exige AX42 idle, no crea planes/recibos, no reconcilia ni ejecuta efectos.
La salud exige contenedor en ejecución y HTTP 200 / `status=UP` del Actuator
local fijo. Si no hay `HEALTHCHECK` Docker (o está explícitamente deshabilitado),
no se inventa esa señal. Si está configurado, debe existir y estar `healthy`;
`starting`, `unhealthy`, estados malformados o una señal ausente no se ocultan
con un Actuator UP. Ninguna lectura ejecuta el comando del `HEALTHCHECK`.
App debe comprobar por separado que ese commit contiene el merge de su ticket.
Un recibo del operador no se convierte en una operación de publicación móvil.
Instalar esta ampliación usa el installer del publicador VPS; no el target
AX42_PLATFORM, ni el installer del worker. El protocolo de efectos no cambia.

El artefacto debe ser del último run push/main exitoso de
`.github/workflows/release-artifacts-v1.yml`, para el SHA exacto de main y el
repositorio fijo. Se verifican digest ZIP GitHub, estructura cerrada,
manifiesto y hash del payload. Un run fallido no se reemplaza por otro PASS
anterior. CI no tiene autoridad ni secretos de PROD/firma.

## Estado y recuperación

App persiste una outbox antes de solicitar efectos. Cada plan y ejecución
tienen UUIDs server-owned estables; EXECUTE exige el hash del plan mostrado
y confirmado. El daemon guarda sus registros root:root 0600 bajo
`/srv/atenea/release-v1/plans/<UUID>/`. Su respuesta pública contiene sólo
identidades, estado, commits, versión y hashes.

PLAN pasa PREPARING→READY y espera hasta 45 minutos si el build main sigue
en curso; READY caduca a los 10 minutos. PREPARING puede descargar/stagear
artefactos, cargar una imagen inactiva o firmar un APK privado, pero no
recrea App, instala Platform ni cambia el manifiesto público.

EXECUTE persiste ACCEPTED/APPLYING antes de instalar. Si se reinicia en
APPLYING, verifica o restaura el predecesor; **no repite apply**. Un rechazo
previo a efectos (caducidad, drift) queda BLOCKED con la misma operation ID.
Los recibos de instalación/rollback, backup y hashes se conservan. Un fallo
de rollback exige intervención explícita; no se autoriza otra publicación.

Platform usa flock exclusivo frente a admisión compartida de AgentRuns,
validación y mutaciones Codex/workspace. El marcador público, sin secretos,
es `/etc/atenea-worker/release-control-v1.installed` (root:root 0644).
El lock `/run/atenea/release-v1/admission.lock` es root:atenea 0640. Sólo la
ausencia legítima del marcador preserva el modo antiguo; un lock/marker
ilegible, symlink o permisos ajenos falla cerrado.

## Bootstrap desde el portátil (no desde un AgentRun)

Requiere autorización de instalación, configuración/secretos, networking,
backup, deploy y APK. Usar los accesos SSH de operador que ya existen.
No copiar la clave SSH personal al worker.

1. Revisar las PRs App/Platform y configurar los prerequisites GitHub del
   documento App `docs/mobile-delivery-v1.md`. Integrar sólo con CI verde.
   Esperar artefactos exitosos e inmutables de los dos merges exactos.
2. Capturar preflight: SHAs reales, salud App/AX42, cero AgentRuns y
   validaciones no terminales, ownership/workspaces y enlaces/inventario
   Codex. Usar la versión **observada**, no fijar 0.145.0 ni activar Codex.
3. En AX42 usar checkout limpio del merge Platform aprobado. Ejecutar el
   installer worker soportado `plan`, después `apply` y `verify`. No
   forzar salvaguardas ni cambiar current/previous/identidades.
4. En ambos hosts preparar `/etc/atenea-release-v1/` root:root 0700, con
   `config.json`, `github.token` y `ax42.token` root:root 0600. El token
   GitHub sólo necesita Contents/Actions read en los dos repositorios; no
   credenciales VPS. El peer token es específico del nuevo protocolo, no
   un token de operador App. Nunca imprimir/copy-pastear secretos en una
   conversación ni guardarlos en Git.
5. AX42: `config.json` debe ser exactamente `{"mode":"AX42"}`. El acceso
   se liga a `100.81.98.93:8791`; sólo acepta `100.88.252.28` y bearer válido
   en `/v1/release`. Ajustar ACL/firewall únicamente para VPS→AX42:8791;
   no abrir 22 ni entregar acceso AX42→VPS.
6. VPS: config exactamente con `mode`, `composeFiles` y
   `androidCertificateSha256`. `composeFiles` es la lista ordenada
   **actual** de ficheros root-controlled en
   `/srv/atenea/platform/stacks/prod/`, incluyendo al final
   `docker-compose.release-v1.json`. Preservar name/proyecto Compose,
   flags, mounts y todas las overrides activas. No arrancar sólo con la
   base, que puede fijar una imagen/flags antiguos. Si la autoridad de los
   ficheros/directorios no es root o está abierta a escritura ajena,
   detenerse; no cambiar propietarios masivamente.
7. La nueva override VPS conserva la configuración efectiva y añade sólo
   al backend el flag `ATENEA_RELEASE_CONTROL_ENABLED=true` y bind
   `/run/atenea/release-v1:/run/atenea/release-v1:ro`. No montar claves,
   config/tokens root ni el almacenamiento de releases en App. Mantener
   UID/GID App 1001; el socket será root:1001 0660.
8. VPS: conservar la firma compatible ya utilizada. Provisionar
   `/etc/atenea-release-v1/android.keystore` y `android-keystore.pass`
   root:root 0600 con la identidad **existente**, y fijar el SHA-256 del
   certificado observado en `androidCertificateSha256`. No generar otra
   clave. Instalar/verificar `apksigner` y `aapt` por el mecanismo de
   herramientas del VPS. `worker.token` root:root 0600 reutiliza el bearer
   worker vigente para smoke autenticado VPS→AX42:8787.
9. Adoptar sin perder el canal Android actual en la raíz fija
   `/srv/atenea/apk-public-secret/android/`. La metadata/APK deben ser
   root-controlled, ficheros 0644 y directorio `releases/` root 0755.
   Mantener el URL/token ya instalado y mapear ese canal a esta raíz en
   el servidor público. Comprobar la descarga anterior ANTES de publicar.
   Si la ruta del canal actual no corresponde, detenerse y resolver la
   instalación inicial; no aceptar una ruta suministrada por App.
10. Con los checkouts Platform limpios exactos en cada host:

    ```bash
    sudo bash ops/release/install-release-control-v1.sh plan
    sudo bash ops/release/install-release-control-v1.sh apply
    sudo bash ops/release/install-release-control-v1.sh verify
    ```

    El root runtime usa `atenea-release-control-v1.service`, independiente
    del backend. No habilitar sudoers para App/AgentRuns: éstos sólo tienen
    el socket local con un protocolo cerrado.
11. En AX42, una vez verificado el worker desde el mismo main exitoso:

    ```bash
    sudo bash ops/release/install-release-control-v1.sh bootstrap-platform
    ```

    Esta operación sólo adopta el código ya instalado después de verificar
    el artefacto/main exactos; no ejecuta apply/restart ni fabrica un
    predecesor. Persiste `platform-current.json` y el artefacto que permite
    rollback. Un baseline existente o foreign se rechaza.
12. VPS: backup fresco/verificado PostgreSQL 16 en la ruta protegida
    `/srv/atenea/backups/prod/` (root 0700). Desplegar App del artefacto
    inmutable exacto mediante el flujo directo existente y toda la lista
    Compose efectiva: `up -d --no-deps --no-build atenea-backend-prod`.
    Preservar PostgreSQL y demás servicios, aplicar V84 y verificar health,
    login, lectura de proyectos y comunicación autenticada App→AX42.
    Habilitar/reutilizar TOTP y grants existentes mediante su procedimiento
    normal si aún faltan; no crear factores/usuarios de conveniencia.
13. Publicar/instalar una primera APK estable con el nuevo panel mediante el
    canal normal y la firma anterior. No es necesario un App DEV.
14. Hacer la aceptación completa **desde móvil** descrita en el documento
    App, con la misma WorkSession/ticket. Hasta que pase, no declarar
    conseguida la operatividad 100% móvil.

Cada salvaguarda real detiene el bootstrap; no fabricar registros,
symlinks, baseline ni successful receipts. Los comandos de installer son
interfaces de operador para esta instalación explícita, nunca argumentos
del protocolo móvil.

## Límites operativos

App cambia sólo el image ID de backend en la override. Hace dump consistente,
SHA-256 y TOC PostgreSQL 16 antes de recrearlo; verifica SHA OCI, health local/
público, Flyway esperado/sin fallos, worker autenticado y PG container/mounts
intactos. La restauración automática revierte **imagen/config**, no DB.
Sólo integrar migraciones expand-only/backward-compatible con la imagen
anterior; ninguna declaración del manifiesto prueba por sí sola esa
compatibilidad. El smoke login/proyectos se verifica desde la App tras el
despliegue; el ejecutor no conserva credenciales de login de operador.

Platform permite sólo el installer de worker y exige preservar los hashes
del estado Codex/configuración retenida. No activa ni cambia versiones
Codex. Una transición de configuración/protocolo que no pueda preservar esa
evidencia requiere su propio procedimiento cerrado y revisión.

Sólo la unidad AX42 permite además `AF_NETLINK`: el installer fijo consulta
la dirección Tailscale y sus listeners mediante `ip`/`ss`. Sin esta familia,
el preflight rechaza incluso un baseline sano antes de crear el plan. La
unidad VPS conserva su allowlist anterior y las demás protecciones no cambian.

Android exige versionCode mayor, package existente y certificado compatible.
Publica generaciones inmutables y sustituye sólo el manifiesto público.
Rollback restaura el canal anterior, **no desinstala** la actualización que
ya haya instalado un móvil. Los APKs/operaciones quedan auditados.

La actualización del propio daemon release-control requiere por ahora el
installer de operador, no el target AX42_PLATFORM. La creación/integración
de PRs Platform desde repository-roles tampoco forma parte de este slice.
Estos límites deben mostrarse como trabajo pendiente, no resolverse dando
shell/SSH arbitrario al agente.
