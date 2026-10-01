# ANDROID_BUILD v2: precache cerrado, ejecución candidata offline

El installer instala manifest, fragmento Dockerfile y preparador 0644 root:root
y verifica sus hashes. El broker reconoce sólo bundles íntegros de diez
archivos revisados; no permite elegir rutas, versiones, comandos ni imágenes.
Rechaza buildSrc, alternativas Groovy y metadata de resolución no revisada,
que podrían cambiar el grafo aunque los .kts conservaran sus hashes.
Sólo los dos literales numéricos de versión APK se normalizan antes del hash
y del precache; no cambian herramientas/dependencias. Subir la versión no
requiere otro rollout Platform. Se rechazan expresiones/interpolaciones y
modificaciones del resto del script. La compilación candidata usa su fuente
original, con la versión real incluida en su fingerprint y evidencia nueva.

El contexto de build contiene únicamente esos archivos de configuración,
el Dockerfile SDK con hash autorizado y el preparador. No se copia código del
ticket, buildSrc, manifest Android candidato, global gradle.properties,
credenciales, keystore ni init scripts. El build genera cinco probes Kotlin
y cuatro tests sintéticos para precargar las dependencias de APK/tests.

Se sella sólo el cache modules-2 de Gradle 8.10.2, excluyendo locks y
gc.properties. Inventario/hash/estructura/owner/mode se verifican antes de
copiarlo. No se adoptan daemon state, task outputs, init scripts ni configuración
global del operador. La copia de caché modular sigue el procedimiento de
[Gradle](https://docs.gradle.org/current/userguide/dependency_caching.html).

La receta incluye un segundo build sintético frío `RUN --network=none`, con
UID 1000/GID 0, caché reubicada y sin .gradle/build anteriores. Esto comprueba
que una caché efectiva, no sólo un `gradle -v`, es requisito del artefacto.
Requiere BuildKit con RUN --network; si no está disponible, falla cerrado.

Después se ejecuta la fuente candidata en un contenedor nuevo, rootless,
network none, read-only, sin capacidades y con límites existentes. Un único
bind fuente read-only; ningún socket, secreto ni caché host. El GID 0 es
interno al contenedor rootless y sólo permite leer el snapshot del slot.

El preparador no root verifica y copia cache a tmpfs privado, copia la fuente
y descarta outputs/local.properties previos. `/work` requiere `exec` para el
AAPT2 extraído de la caché de Gradle; se habilita explícitamente sólo en ese
tmpfs privado, mientras `/tmp` permanece `noexec` y no se añade ningún bind.
Gradle ejecuta `:app:assembleDebug`
y `testDebugUnitTest` para todos los módulos, offline y sin elegir tasks del
llamante. No firma ni publica una versión estable y no inicia AgentRuns.

La imagen se ejecuta/retira por digest observado, y el contenedor por su ID.
Preparación/caché/recursos son infraestructura; compilación/tests identificados
son candidato; un exit desconocido no prueba que el ticket esté mal. La limpieza
fallida bloquea el PASS. Los diagnósticos simbólicos y hashes son durables.

Los receipts Android v1 terminales siguen consultables, pero no se reejecutan
ni satisfacen Android v2. El perfil App v2 mantiene las cuatro etapas requeridas.

Tests focales (sin Docker real):

```sh
python3 ops/worker/test-atenea-android-validation-v2.py
python3 ops/worker/test-atenea-validation-v1.py
python3 ops/worker/test-closed-validation-broker-contract-v1.py
bash ops/worker/test-install-agent-run-worker-v1.sh
```

Antes de integrar: build real de la receta para los bundles revisados,
compilación candidata/APK y tests offline, con loopback HTTP dentro del
contenedor; verificación root real de ownership y retirada. No ejecutar apply,
un nuevo run real o una validación de WS21 como sustituto de estas pruebas.
App debe ejecutar validate-change tras commit y respetar el plan UFD.
