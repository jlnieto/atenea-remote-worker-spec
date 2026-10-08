# BACKEND_TEST v2 y diagnóstico durable

La definición backend v2 necesita PostgreSQL y loopback HTTP aislados para
los tests del repo Atenea.

El installer instala `atenea-backend-test-v2.Dockerfile` y
`atenea-backend-test-v2.py` root-owned 0644 y comprueba sus fingerprints. El
broker hace una construcción rootless desde esos dos archivos y un pom con
hash autorizado. La construcción no recibe el resto del snapshot candidato.

Los coordinadores de preparación backend/Android/web/Playwright permiten `AF_UNIX AF_INET AF_INET6`:
el proveedor de tokens de registro de BuildKit se ejecuta en el cliente y
necesita DNS/HTTPS para preparar la receta confiable. Permitir sólo Unix
bloqueaba la descarga antes de los tests. No se añade `AF_NETLINK`, no cambia
los límites del sandbox y los contenedores candidatos conservan
`--network none`, Maven/Gradle/npm offline y la ausencia de sockets/secretos host.

## Preparación web cerrada

`WEB_BUILD` conserva su revisión `atenea-web-build-v1`, pero ya no depende de
Node/npm instalados en el directorio personal del operador. Su imagen rootless
usa Node 22 fijado por digest, la receta `atenea-web-validation-v1.Dockerfile`
y el preparador `atenea-web-runtime-v1.py`, ambos root-owned y verificados por
el installer y el broker. Sólo dos manifiestos npm con hashes autorizados
entran en la preparación con red: [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
se ejecuta con `--ignore-scripts`, sin configuración ni fuentes candidatas.

La compilación real usa `scripts/web-build.sh` autorizado, UID 1000/GID 0,
imagen read-only, red deshabilitada y tmpfs privados. Se descartan outputs,
`node_modules`, `.npmrc`, `.env*` y cachés de compilador candidatos. La
configuración npm de usuario/global es vacía y usa rutas distintas. Cambiar
manifiestos, la receta o el script exige revisión explícita; no hay rutas,
comandos ni versiones seleccionables por el cliente.

La fase de build previa a Playwright usa esta misma preparación, sin ampliar
los mounts del navegador. El HTML/assets se transfieren como una proyección
acotada y validada antes de escribir en el scratch: sin tar candidato,
symlinks, traversal ni colisiones archivo/directorio. El resultado backend
ya aprobado no se invalida por desplegar esta corrección Platform.

La ejecución usa la imagen observada por digest, UID 1000/GID 0, network none,
cap-drop ALL, no-new-privileges, imagen read-only, tmpfs limitado y un único
mount fuente read-only. El GID 0 es interno al contenedor rootless y permite
leer el snapshot cuyo grupo host es el slot; no concede autoridad host.
Los tests que crean repositorios Git usan sólo `/workspace` en tmpfs privado
(`ATENEA_WORKSPACE_ROOT=/workspace/repos`), sin bind del workspace real. Los
tmpfs de `/work` (5 GiB), `/workspace` (512 MiB) y `/tmp` (512 MiB) suman el
límite de 6 GiB. El pool JDBC de test se limita a cinco conexiones y cero
conexiones ociosas mínimas para no agotar el PostgreSQL efímero al crear
varios contextos Spring.

La precarga Maven de la imagen usa un mirror fijo con identidad `central` para
todos los repositorios declarados por POMs transitivos. Así el cache sellado
puede resolverse después offline: un artefacto descargado bajo otro repository
ID se considera presente pero no disponible para `central`. Además de los
plugins, se resuelve explícitamente la clausura de dependencias de test; el
objetivo `dependency:go-offline` por sí solo no precargó todos los jars del
classpath real.
El launcher de JUnit que Surefire solicita al ejecutar tests también queda
precargado en la versión fijada por el pom autorizado.

El preparador crea una DB PostgreSQL 16 exclusivamente local, copia el cache
Maven y la fuente a tmpfs. Descarta `.git`, `target/` y cachés/outputs Android
previos, para que clases antiguas o permisos del checkout no determinen el
resultado. Después el broker ejecuta la suite completa offline.
No hay App DEV, bind de DB host, token, clave, socket Docker ni red externa
durante la ejecución candidata. La retirada usa únicamente las identidades de
contenedor e imagen creadas/observadas en la operación y falla cerradamente.

Una variación de pom exige actualizar explícitamente la toolchain revisada;
un cliente no puede elegir una receta, versión o imagen. Mantener revisión v2
en ambos extremos. Los registros terminales v1 se conservan sólo para
consulta/replay terminal, nunca ejecución ni satisfacción de evidencia v2.

Cada ejecución completada publica atómicamente un diagnóstico root-only con
fase, código simbólico, exit, hashes e identidades de clases. No se publica
stdout candidato, variables o paths. El manifest incluye el hash de ese
diagnóstico. El broker preserva únicamente resúmenes simbólicos allowlisted.
El stdout original se descarta; no afirmar que un hash permite recuperarlo.

Los registros durables continúan en los directorios privados originales. Los
snapshots/contextos temporales van exclusivamente a
`/srv/atenea/validation-runtime-v1` (root:root 0711), con un directorio por
operation UUID root:slot 0710. Sólo el slot admitido puede atravesarlo; la
fuente y las recetas son root-owned y group-read/execute, nunca group-write.
No se abren permisos ni ACLs en `/srv/atenea/artifacts`. Poner un contexto
group-readable debajo de esos padres privados no lo hacía accesible al CLI
ni al daemon rootless: el intento del 2026-10-07 falló antes de los tests.

Cada operación usa además su propio `DOCKER_CONFIG` slot-owned 0700 en ese
scratch. El cliente recibe un entorno cerrado y el socket rootless fijo; no
importa contextos, credenciales, plugins de usuario ni variables Docker del
coordinador. Buildx puede escribir sus metadatos ahí sin abrir el HOME que la
unidad durable mantiene read-only. El scratch se retira al terminar; los
diagnósticos permanecen root-only en su ubicación durable anterior.

Tests focales sin servicios reales:

```sh
python3 ops/worker/test-atenea-backend-test-v2.py
python3 ops/worker/test-validation-slot-staging-v1.py
python3 ops/worker/test-atenea-validation-v1.py
python3 ops/worker/test-closed-validation-broker-contract-v1.py
bash ops/worker/test-install-agent-run-worker-v1.sh
```

La regresión de permisos usa únicamente fixtures temporales. Ejecutarla como
root permite comprobar DAC con los usuarios de slot existentes, sin crearlos,
modificar el runtime instalado ni iniciar una validación/AgentRun. Incluye el
rechazo de ACLs adicionales/default, symlinks, propietarios, modos y UUIDs
ajenos, y conserva los permisos privados de la evidencia.

Smoke de operador opt-in (requiere autorización de efectos en AX42):

```sh
sudo env ATENEA_TOOLCHAIN_NETWORK_SMOKE=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 ops/worker/test-validation-toolchain-network-v1.py
```

Reutiliza las propiedades exactas del coordinador durable, prepara la receta
backend real y ejecuta sólo un test sintético offline con PostgreSQL privado.
Verifica ausencia de ruta de red externa y de autoridad host en el contenedor.
No ejecuta el ticket ni crea WorkSessions/AgentRuns/evidencia de validación App;
exige cero operaciones activas, mantiene el gate exclusivo de operador y retira
scratch/contenedor/imagen mediante las identidades observadas. Los caches Docker
de dependencias revisadas pueden persistir; no se hace prune global.

La imagen backend se construyó y ejecutó realmente el 2026-09-30. Su DB
PostgreSQL 16 privada, caché Maven sellada y ejecución offline funcionaron.
La primera ejecución reveló límites ausentes de `/workspace` y del pool JDBC,
además de fixtures de test obsoletos. Corregidos esos puntos sin omitir tests,
el `main` App `4815028` termina **989/989 PASS** y el candidato **993/993
PASS**, incluido un run desde el checkout directo con el nuevo preparador.
La preparación limpia también se prueba con un puntero `.git` inválido y
outputs previos. Los 25 tests del mediador incluyen un smoke root real
systemd/Bubblewrap opt-in en el dedicado; no se aplicó el installer.

ANDROID_BUILD v2 añade precache cerrado de dependencias; consultar
`README-atenea-android-validation-v2.md`. La receta Android real y su
compilación candidata offline también pasan. Ambos extremos deben desplegarse
coordinadamente antes de declarar operativo el corredor; el PASS local no
sustituye la evidencia durable y el smoke posterior a rollout.
