# Atenea

Documentos clave:

- `docs/atenea-v2/README.md`: programa maestro V2, arquitectura modular,
  estados, contratos, dependencias, migraciones, pruebas, rollout, rollback y
  puertas humanas; planificación solamente, sin implementación iniciada
- `docs/remote-codex-platform-program.md`: ledger canónico del programa para separar Atenea control plane y el worker Codex remoto
- `docs/remote-codex-platform-baseline.md`: línea base verificada de portátil, Atenea, AX42, repositorios, `dev` y riesgos de migración
- `docs/remote-codex-platform-phases.md`: gates de entrada, evidencia, rollback y archivo de cada fase del programa remoto
- `docs/remote-codex-platform-acceptance.md`: matrices de paridad, capacidad, recuperación, UI móvil/web y rollback
- `docs/atenea-core.md`: definición canónica de `Atenea Core`, su relación con `WorkSession` y el siguiente bloque recomendado
- `docs/atenea-core-foundation-design.md`: diseño técnico implementable para el primer contrato de `Atenea Core Foundation`
- `docs/atenea-core-development-operator-surface.md`: siguiente bloque recomendado para convertir `Atenea Core` en la superficie operativa del dominio `development`
- `docs/roadmap.md`: estado real actual, bloques completados y gaps abiertos
- `docs/atenea-v1-architecture.md`: dirección arquitectónica general
- `docs/worksession-phase1.md`: estado real actual del core `WorkSession`
- `docs/worksession-target-flow.md`: objetivo canónico de producto para el siguiente gran bloque `WorkSession`
- `docs/mobile-server-operations.md`: contrato operativo para pruebas headless, servidores gestionados y despliegues desde móvil
- `docs/project-runtime-verification.md`: contrato por proyecto para verificar runtime y pruebas de navegador desde Atenea Core
- `docs/android-worksession-premium-operation.md`: contrato de calidad para operar WorkSession end-to-end desde Android nativo
- `docs/codex-auth-and-costs.md`: contrato de autenticacion ChatGPT para Codex App Server y lectura movil de costes API
- `docs/session-speech-briefing.md`: briefing con DeepSeek para lecturas TTS utiles de respuestas Codex
- `docs/voice-command-telemetry.md`: telemetria de comandos de voz fallidos para mejorar el interprete
- `docs/voice-engine/README.md`: contrato de producto, arquitectura y plan del motor de voz premium de Atenea
- `android/README.md`: estado y guía operativa del nuevo cliente Android nativo
- `docs/session-deliverables-design.md`: diseño objetivo para deliverables persistidos, reporting y pricing de sesión
- `docs/task-branch-workflow.md`: referencia histórica del flujo retirado `Task` / `TaskExecution`
- `AGENTS.md`: guía local canónica para agentes/Codex

Workflow de desarrollo para este VPS:

```bash
./scripts/test.sh
./scripts/run.sh
./scripts/build.sh
./scripts/deploy-preview.sh
./scripts/deploy-prod.sh
./scripts/release.sh
./scripts/android-build.sh
./scripts/android-publish-apk.sh
./scripts/shell.sh
./scripts/logs-db.sh
./scripts/logs-codex.sh
./scripts/down.sh
```

Cliente Android nativo:

```bash
./scripts/android-build.sh
```

Bootstrap local de operador móvil:

```bash
ATENEA_AUTH_BOOTSTRAP_ENABLED=true \
ATENEA_AUTH_BOOTSTRAP_EMAIL=operator@atenea.local \
ATENEA_AUTH_BOOTSTRAP_PASSWORD=secret-pass \
./scripts/run.sh
```

Habilitar envío real de push móvil FCM:

```bash
ATENEA_MOBILE_PUSH_ENABLED=true \
ATENEA_MOBILE_PUSH_FCM_PROJECT_ID=atenea-mobile \
ATENEA_MOBILE_PUSH_FCM_CLIENT_EMAIL=firebase-adminsdk@atenea-mobile.iam.gserviceaccount.com \
ATENEA_MOBILE_PUSH_FCM_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n' \
./scripts/run.sh
```

Habilitar voz OpenAI para `Atenea Core`:

```bash
ATENEA_OPENAI_ENABLED=true \
ATENEA_OPENAI_API_KEY=sk-... \
./scripts/run.sh
```

## Qué hace cada script

Los scripts resuelven automáticamente la variante de Compose disponible: primero intentan
`docker compose` y, si no existe, usan `docker-compose`.

- `./scripts/test.sh`
  Ejecuta la suite Maven dentro de Docker con JDK 21. No requiere Java instalado en el host.
  Es la vía canónica para tests y debe preferirse sobre ejecutar `./mvnw` directamente desde el host.

- `./scripts/run.sh`
  Levanta la base de datos de desarrollo y arranca Spring Boot dentro de Docker exponiendo el puerto host `8085` por defecto.

- `./scripts/build.sh`
  Genera el `jar` dentro de Docker y no repite tests por defecto. Usa `./scripts/test.sh` para validación; si necesitas un package con tests, ejecuta `ATENEA_BUILD_RUN_TESTS=true ./scripts/build.sh`.

- `./scripts/deploy-preview.sh`
  Reconstruye y levanta el backend de preview desde `/srv/atenea/platform/stacks/preview` y verifica `/actuator/health`.

- `./scripts/deploy-prod.sh`
  Reconstruye y levanta el backend de producción desde `/srv/atenea/platform/stacks/prod` y verifica `/actuator/health`.

- `./scripts/release.sh`
  Ejecuta tests, build backend, deploy preview y deploy producción. Si `ATENEA_RELEASE_PUBLISH_APK=true`, también compila y publica APK.

- `./scripts/android-build.sh`
  Compila la app Android nativa de `android/` dentro de Docker con Android SDK y Gradle. Por defecto ejecuta `:app:assembleDebug`.

- `./scripts/android-publish-apk.sh`
  Publica el APK debug Android ya compilado en `/srv/atenea/apk-public/atenea-debug.apk` para descarga protegida desde `https://atenea.yudri.es/apk/atenea-debug.apk`.

- `./scripts/shell.sh`
  Abre una shell Bash dentro del contenedor de desarrollo con el repo montado.

- `./scripts/logs-db.sh`
  Sigue los logs de PostgreSQL de desarrollo.

- `./scripts/logs-codex.sh`
  Sigue los logs del servicio `codex-app-server` del stack de desarrollo.

- `./scripts/down.sh`
  Baja el stack definido en `docker-compose.dev.yml`.

## Stack principal

`docker-compose.dev.yml` levanta:

- `db`: PostgreSQL para desarrollo
- `codex-app-server`: servicio `codex app-server` aislado en Docker
- `atenea-dev`: contenedor de desarrollo con JDK 21, workspace montado y caché Maven persistente

## Estado actual

Atenea hoy tiene dos lecturas que deben mantenerse separadas para no mezclar objetivo con runtime.

Lectura de producto objetivo:

- `Atenea Core` es la futura capa superior conversacional
- `Atenea Core` debe enrutar entre dominios como `development`, `operations` y `communications`
- `WorkSession` debe quedar como workflow del dominio `development`

Lectura de runtime actual del repo:

- el backend Spring Boot implementado hoy sigue siendo development-first, con un primer slice runtime de `operations`
- existe un primer slice runtime de `Atenea Core Foundation`
- ese slice enruta el dominio `development` y capacidades operativas iniciales de `operations`
- `WorkSession` sigue siendo la única superficie de workflow real por debajo del core

El modelo backend activo hoy es:

- `Project`
- `CoreCommand`
- `WorkSession`
- `SessionTurn`
- `AgentRun`
- `POST /api/core/commands` como entrada top-level inicial
- dominio `operations` inicial para hosts gestionados, checks HTTP externos, incidentes y recuperación controlada de Apache por SSH
- apertura o resolución de sesión
- turnos conversacionales con Codex
- continuidad de thread
- historial de turns y runs
- publish a pull request
- sync de pull request
- cierre fuerte con reconciliación

El flujo legacy `Task` / `TaskExecution` ya fue retirado del backend y de la base de datos.

Conclusión operativa:

- hoy el repo implementa el dominio `development` y un slice inicial del dominio `operations`
- `Atenea Core Foundation` más la superficie operativa de `development` ya existen en backend
- el backend de core ya soporta:
  - estado de proyectos
  - selección de proyecto activo
  - apertura y continuidad de `WorkSession`
  - publish
  - sync PR
  - deliverables
  - close
  - aclaraciones
  - confirmaciones
  - `speakableMessage`
  - timeline de comandos
- el siguiente bloque ya no es “crear core”, sino endurecer la operación móvil, la configuración segura de hosts gestionados y los runbooks remotos
- no debe documentarse como si ya soportara `communications` en runtime

La superficie móvil soportada es la app Android nativa en `android/`. El backend y los contratos `Atenea Core` / `/api/mobile/*` siguen siendo la fuente de verdad.

## Superficies API actuales

Hoy el backend expone dos superficies funcionales reales:

- `Project`
  - registro y listado de repositorios operables
  - bootstrap de proyectos canónicos
  - `defaultBaseBranch` por proyecto
  - overview agregado del estado de proyecto
- `Billing`
  - cola comercial global sobre `PRICE_ESTIMATE` aprobado
  - filtros por estado, proyecto, sesión y búsqueda textual
  - summary de pendientes y facturados por moneda
- `Mobile`
  - auth móvil de operador con login, refresh, logout y `me`
  - registro de dispositivos push FCM por operador
  - dispatch backend de notificaciones FCM para eventos clave de operación móvil
  - overview móvil de proyectos
  - inbox móvil de atención operativa
  - summary y feed de eventos por sesión
  - aliases móviles para operación completa de sesión, deliverables y billing
- `WorkSession` / `SessionTurn` / `AgentRun`
  - apertura o resolución de sesión
  - branch de trabajo propio por sesión
  - vistas agregadas de sesión
  - turnos conversacionales con Codex
  - continuidad de thread
  - historial de turns y runs
  - publish a PR
  - sync de PR
  - cierre fuerte con reconciliación final

Referencias:

- `docs/worksession-phase1.md`: superficie conversacional `WorkSession`
- `docs/worksession-target-flow.md`: ruta objetivo de `WorkSession` como flujo completo de trabajo
- `docs/roadmap.md`: estado consolidado y gaps reales abiertos

## Arquitectura funcional actual

`WorkSession` debe leerse en este README como:

- la superficie runtime actual del backend
- el workflow del dominio `development` que más adelante será orquestado por `Atenea Core`

### Core `WorkSession`

Actualmente ya implementa:

- persistencia de `work_session`, `session_turn` y `agent_run`
- una sola sesión `OPEN` por proyecto
- una sola run `RUNNING` por sesión
- `defaultBaseBranch` a nivel de `Project`
- `POST /api/projects/{projectId}/sessions`
- `POST /api/projects/{projectId}/sessions/resolve`
- `POST /api/projects/{projectId}/sessions/resolve/view`
- `POST /api/projects/{projectId}/sessions/resolve/conversation-view`
- `GET /api/sessions/{sessionId}`
- `GET /api/sessions/{sessionId}/view`
- `GET /api/sessions/{sessionId}/conversation-view`
- `POST /api/sessions/{sessionId}/turns`
- `POST /api/sessions/{sessionId}/turns/conversation-view`
- `GET /api/sessions/{sessionId}/turns`
- `GET /api/sessions/{sessionId}/runs`
- `POST /api/sessions/{sessionId}/publish`
- `POST /api/sessions/{sessionId}/publish/conversation-view`
- `POST /api/sessions/{sessionId}/pull-request/sync`
- `POST /api/sessions/{sessionId}/pull-request/sync/conversation-view`
- `POST /api/sessions/{sessionId}/close`
- `POST /api/sessions/{sessionId}/close/conversation-view`
- `GET /api/sessions/{sessionId}/deliverables`
- `GET /api/sessions/{sessionId}/deliverables/approved`
- `GET /api/sessions/{sessionId}/deliverables/price-estimate/approved-summary`
- `GET /api/sessions/{sessionId}/deliverables/types/{type}/history`
- `GET /api/sessions/{sessionId}/deliverables/{deliverableId}`
- `POST /api/sessions/{sessionId}/deliverables/{type}/generate`
- `POST /api/sessions/{sessionId}/deliverables/{deliverableId}/approve`
- `POST /api/sessions/{sessionId}/deliverables/{deliverableId}/billing/mark-billed`
- `GET /api/projects/{projectId}/approved-price-estimates`
- `GET /api/billing/queue`
- `GET /api/billing/queue/summary`
- `GET /api/mobile/projects/overview`
- `POST /api/mobile/auth/login`
- `POST /api/mobile/auth/refresh`
- `POST /api/mobile/auth/logout`
- `GET /api/mobile/auth/me`
- `POST /api/mobile/notifications/push-token`
- `POST /api/mobile/notifications/push-token/unregister`
- `GET /api/mobile/notifications/push-devices`
- dispatch backend a FCM para:
  - `RUN_SUCCEEDED`
  - `CLOSE_BLOCKED`
  - `PULL_REQUEST_MERGED`
  - `BILLING_READY`
- `GET /api/mobile/inbox`
- `GET /api/mobile/inbox/stream`
- `GET /api/mobile/operations/hosts`
- `GET /api/mobile/operations/hosts/{hostId}/status`
- `GET /api/mobile/operations/incidents`
- `GET /api/mobile/sessions/{sessionId}/summary`
- `GET /api/mobile/sessions/{sessionId}/events`
- `GET /api/mobile/sessions/{sessionId}/events/stream`
- `POST /api/mobile/projects/{projectId}/sessions/resolve`
- `GET /api/mobile/sessions/{sessionId}/conversation`
- `POST /api/mobile/sessions/{sessionId}/turns`
- compatibility aliases only:
  - `POST /api/mobile/sessions/{sessionId}/publish`
  - `POST /api/mobile/sessions/{sessionId}/pull-request/sync`
  - `POST /api/mobile/sessions/{sessionId}/close`
- `GET /api/mobile/sessions/{sessionId}/deliverables`
- `GET /api/mobile/sessions/{sessionId}/deliverables/approved`
- compatibility aliases only:
  - `POST /api/mobile/sessions/{sessionId}/deliverables/{type}/generate`
  - `POST /api/mobile/sessions/{sessionId}/deliverables/{deliverableId}/approve`
  - `POST /api/mobile/sessions/{sessionId}/deliverables/{deliverableId}/billing/mark-billed`
- `GET /api/mobile/billing/queue`
- `GET /api/mobile/billing/queue/summary`
- `workspaceBranch` real por sesión con convención `atenea/session-{id}`
- fallback de `baseBranch`:
  - `request.baseBranch`
  - si no viene, `project.defaultBaseBranch`
  - si tampoco existe, branch actual del repo
- recuperación estricta del branch de sesión:
  - permitida desde `baseBranch` limpia
  - permitida si el repo ya está en `workspaceBranch`
  - bloqueada si el repo está en una tercera rama
- continuidad de `externalThreadId` entre turns
- reconciliación de runs `RUNNING` stale al recargar estado de sesión
- metadatos de delivery persistidos en sesión:
  - `pullRequestUrl`
  - `pullRequestStatus`
  - `finalCommitSha`
  - `publishedAt`
- estados de cierre:
  - `OPEN`
  - `CLOSING`
  - `CLOSED`
- cierre fuerte:
  - bloqueo si hay runs activos
  - bloqueo si hay cambios no publicados
  - bloqueo si la PR no está mergeada
  - vuelta obligatoria a rama principal del proyecto alineada con remoto
  - eliminación de rama local de sesión
  - eliminación de rama remota cuando aplica
- estado persistido de bloqueo de cierre:
  - `closeBlockedState`
  - `closeBlockedReason`
  - `closeBlockedAction`
  - `closeRetryable`
- subsistema de deliverables de sesión:
  - `WORK_TICKET`
  - `WORK_BREAKDOWN`
  - `PRICE_ESTIMATE`
- versionado por tipo de deliverable
- generación explícita por deliverable con snapshot persistido
- aprobación manual de una versión concreta
- `SUPERSEDED` para versiones anteriores regeneradas o reemplazadas
- `PRICE_ESTIMATE` con:
  - Markdown revisable
  - `contentJson` estructurado y validado
  - lectura rápida de pricing aprobado por sesión
  - lectura agregada de pricing aprobado por proyecto
  - estado comercial persistido:
    - `READY`
    - `BILLED`
  - `billingReference` y `billedAt` sobre la baseline aprobada
- vistas agregadas para frontend:
  - `WorkSessionViewResponse`
  - `WorkSessionConversationViewResponse`
  - contrato primario recomendado para operador/frontend:
    - `WorkSessionConversationViewResponse`
- snapshot descriptivo de repositorio en `WorkSessionResponse` con:
  - `repoValid`
  - `workingTreeClean`
  - `currentBranch`
  - `runInProgress`

## Overview de proyecto

`GET /api/projects/overview` ya es session-first:

- bloque `workSession` con la sesión canónica del proyecto
  - `OPEN` o `CLOSING` si existe una activa
  - o la más reciente por `lastActivityAt`

El overview ya no expone bloques legacy.

## Deliverables y pricing

El backend ya no está sólo en fase de read model para deliverables. Hoy implementa:

- generación explícita de:
  - `WORK_TICKET`
  - `WORK_BREAKDOWN`
  - `PRICE_ESTIMATE`
- snapshot persistido de evidencia de sesión por versión
- historial por tipo:
  - `GET /api/sessions/{sessionId}/deliverables/types/{type}/history`
- aprobación manual:
  - `POST /api/sessions/{sessionId}/deliverables/{deliverableId}/approve`
- latest approved set:
  - `GET /api/sessions/{sessionId}/deliverables/approved`

`PRICE_ESTIMATE` tiene además una capa estructurada para explotación operativa:

- `contentJson` validado en backend
- `billingStatus`, `billingReference` y `billedAt` persistidos sobre la versión aprobada
- resumen aprobado por sesión:
  - `GET /api/sessions/{sessionId}/deliverables/price-estimate/approved-summary`
- lista de pricing aprobado por proyecto:
  - `GET /api/projects/{projectId}/approved-price-estimates`

La UI web ya consume estas superficies para:

- generar deliverables
- revisar versiones
- aprobar versiones
- consultar baseline de pricing aprobado de la sesión
- consultar pricing aprobado histórico del proyecto

## Notas operativas

- El host no necesita Java para desarrollar Atenea en este VPS.
- Los comandos Maven deben ejecutarse a través de los scripts de `scripts/`.
- Para tests, la entrada canónica es `./scripts/test.sh`.
- En desarrollo, `atenea-dev` y `codex-app-server` comparten el workspace canónico del host:
  - `/srv/atenea/workspace/repos` montado en `/workspace/repos`
  - `/srv/atenea/workspace/context` montado en `/workspace/context` en solo lectura
  - `/srv/atenea/workspace/codex-home` montado en `/workspace/codex-home`
- El workspace root es configuración de plataforma mediante `ATENEA_WORKSPACE_ROOT` y en este stack vale `/workspace/repos`.
- La estructura esperada del workspace es `/workspace/repos/internal/...`, `/workspace/repos/clients/...` y `/workspace/repos/sandboxes/...`.
- En desarrollo, el `repoPath` correcto para Atenea es `/workspace/repos/internal/atenea`.
- `repoPath` no es opcional. Debe:
  - ser absoluto
  - estar dentro del `workspaceRoot` configurado
  - existir
  - ser un directorio
  - contener `.git`
- `codex app-server` usa un `HOME` dedicado bajo `/workspace/codex-home`.
- La base de desarrollo usa por defecto:
  - base de datos: `atenea`
  - usuario: `atenea`
  - password: `atenea`
  - puerto host: `5434`
- La app de desarrollo expone por defecto el puerto host `8085`. Producción usa `8081` y preview usa `8082`.
