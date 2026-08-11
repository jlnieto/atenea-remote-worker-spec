# Auditoría de partida de Atenea V2

Fecha: 2026-08-11.

Modo: sólo lectura. No se creó ni modificó una WorkSession, AgentRun, prompt,
runtime, preview, APK, migración, servicio, configuración, repo remoto o
recurso de AX42/producción.

## Fuentes examinadas

- instrucciones `AGENTS.md` aplicables;
- programa, baseline, fases, aceptación y ledger remoto;
- arquitectura V1, Core/operator surface, mobile operations, runtime
  verification y Android operation;
- las doce especificaciones OpenSpec canónicas;
- propuestas/diseños/tareas archivados de cierre remoto, adjuntos Android y
  sandbox de instrucciones;
- código, tests y migraciones hasta V66 de la fuente aceptada de Atenea;
- Git local/origin/control, PostgreSQL productivo dentro de transacción
  `READ ONLY ... ROLLBACK`, containers/health/config y metadatos sanitizados de
  AX42.

No se examinaron prompts, respuestas, contenido de adjuntos, `auth.json`,
tokens, cookies, credenciales, historial de Codex ni dumps de entorno.

## Qué ya funciona y debe reutilizarse

### Dominio conversacional

- `Project`, `WorkSession`, `SessionTurn` y `AgentRun` son el modelo activo.
- WorkSession conserva branch, thread, turns, runs, delivery y cierre.
- AgentRun remoto ya tiene queue/start/run/cancel/reconcile y estados
  terminales, leases, revisiones, dispatch y progreso durables.
- `process_outcome` ya separa parcialmente el final del proceso de la
  aceptación.

### Fuente, validación y aceptación

- WorkSession persiste fingerprint de fuente, revisión de definición,
  proyección de validación y estados `DRAFT/VALIDATING/BLOCKED/VALIDATED/
  INTEGRATION_READY`.
- `validation_operation` ya representa checks simbólicos
  `BACKEND_TEST/WEB_BUILD/ANDROID_BUILD/PLAYWRIGHT_ACCEPTANCE` ligados a un
  fingerprint exacto.
- `closed_validation_operation` y tests existentes prueban que la validación
  debe ser cerrada y no aceptar comandos arbitrarios.
- El runner conserva instrucciones revisadas, source exacto y draft retention.

### Worker y ownership

- AX42 dispone de cuatro slots rootless, dos permisos heavy, admission y
  allocation persistidos.
- Mirrors/worktrees son por remote WorkSession con ownership y fingerprint.
- El cierre remoto es durable, idempotente y monótono; `CLOSED` depende de Git
  y receipt `RELEASED`.
- Fresh-session durable permite sucesor vacío cuando avanza fuente sin copiar
  conversaciones o adjuntos.
- Backups cifrados, backup-check, health timers y RAID están operativos.

### Adjuntos, previews y evidencia

- Adjuntos reales de WorkSession están ligados a proyecto/sesión/worker/
  remote session/storage scope y tienen límites/retención.
- Preview privado ya tiene estados, leases, revisions, ownership y
  reconciliación.
- Playwright y browser artifacts existen en los contratos del worker.

### Operación y clientes

- Atenea Core tiene capabilities tipadas, aclaración, confirmación, timeline y
  contexto de operador.
- Android y web ya operan WorkSession y adjuntos.
- Producción, preview y Beautips están detrás de Caddy y health verificable.

Estas piezas no se reescriben. V2 las envuelve, evoluciona o conecta mediante
migraciones compatibles.

## Debilidades estructurales verificadas

### 1. Una sesión abierta por proyecto

La migración V15 creó `uk_work_session_open_project`, y `WorkSessionService`
bloquea si existe una sesión `OPEN` o `CLOSING`. Por tanto, hoy no es posible
modelar correctamente dos cambios independientes sobre dos ramas del mismo
proyecto.

Decisión V2: introducir `DevelopmentChange` y mover la exclusión a “una
WorkSession abierta por cambio”, conservando el constraint legacy hasta una
fase contract demostrada.

### 2. WorkSession concentra demasiadas responsabilidades

La entidad contiene conversación, worker/workspace, source/draft,
acceptance/validation, PR/delivery y close remoto. Es correcto para el flujo
actual, pero no escala a varios ciclos de conversación, validación, revisión e
integración del mismo cambio.

Decisión V2: WorkSession sigue siendo contexto conversacional; las
proyecciones de ciclo de entrega pasan al cambio y a recursos específicos.

### 3. Dos superficies de validación no unificadas

`validation_operation` implementa el contrato cerrado moderno, mientras
`project_verification_run`/`ProjectVerificationService` es un flujo anterior
que lee strings `testCommand`, `startCommand`, `browserTestCommand` y ejecuta
familias allowlisted desde el backend. La documentación histórica incluso
describe Docker CLI/socket en producción.

Decisión V2:

- evolucionar `validation_operation` como predecessor del `ValidationRun` V2;
- añadir `ValidationPlan` y remote lease/receipt, no otro resultado paralelo;
- dejar `project_verification_run` legacy/read-only y no enrutar V2 por él;
- mover la ejecución a un broker AX42 rootless con definiciones server-owned;
- mantener Docker ausente en AgentRun y backend productivo.

### 4. Éxito de proceso aún puede confundirse con listo para entregar

Aunque V52 separó proceso y aceptación, UI y flujo siguen siendo session-first
y no existe una cadena completa y única fuente → validation → review →
integration → release.

Decisión V2: estados ortogonales, manifests exactos y readiness derivada por
servidor.

### 5. Artefactos de build no tienen catálogo de release

Adjuntos resuelven conversación y evidencia, pero no existe un agregado
inmutable de artefactos con source/toolchain/provenance/eligibility. Un APK de
test y uno firmado/publicado no están modelados como derivaciones distintas.

Decisión V2: `Artifact`/`ArtifactManifest` separados y signing como derivación
privilegiada.

### 6. Preview no equivale a aceptación

El preview actual es WorkSession-centric y su readiness no representa una
decisión humana ligada a validación exacta.

Decisión V2: conservar el lifecycle privado, añadir `ReviewEnvironment` por
cambio y `ReviewDecision` durable/stale-aware.

### 7. Deploy sigue siendo una disciplina operativa externa

Los rollouts recientes son robustos porque usan manifests, hashes,
preflight/rollback y autorizaciones exactas, pero ese patrón no es aún un
recurso de producto. Core operations histórico acepta runbooks limitados, no
un lifecycle general de release artifact.

Decisión V2: modelar candidate/plan/authorization/operation y mantener el
executor productivo separado de Codex/validación.

### 8. La cuenta única no tiene step-up fuerte

La única cuenta activa es `PLATFORM_ADMINISTRATOR`. Login usa password,
access JWT breve y refresh tokens hash/one-shot. Se observaron ocho refresh
sessions válidas. No existe passkey, familia de dispositivo visible, replay
family detection ni autorización de un solo uso ligada al target.

Decisión V2: passkey/WebAuthn, sesión familiar rotatoria, inventario/revocación,
credential/role version y action-bound step-up. Tener un solo usuario no reduce
el impacto de una sesión robada.

### 9. Core confirmation no sustituye autorización privilegiada

Core dispone de `requiresConfirmation` y token de confirmación, pero confirmar
intención dentro de una sesión autenticada no prueba de nuevo presencia para
una acción productiva.

Decisión V2: conservar confirmación UX y exigir además step-up para gates
privilegiados.

### 10. Documentación histórica contiene estado obsoleto

Algunos documentos aún afirman que AgentRuns no llegan a AX42, que adjuntos o
cierre remoto faltan, o que el backend es la superficie normal de build. El
ledger y specs posteriores demuestran lo contrario.

Decisión V2: el programa maestro y cambios activos declaran autoridad; los
documentos anteriores se conservan como historia, no como runtime truth.

## Estado live exacto relevante

### Git

- programa base local/remoto: `90b4572c7e0fc38b3c8addfee241033858ea54e8`;
- checkout de control limpio: `ae225688dae8e816a4795fc2dcd1bb6bdb724c95`;
- app local limpia/publicada: `39d7d7379423b3da36ce89cc3329cbc6f87f00b3`;
- app control `main`: `e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`.

### Base de datos

- Flyway V66 successful;
- WS16 `CLOSED/RELEASED/10/DRAFT`;
- WS17 `CLOSED/RELEASED/6/DRAFT`;
- WS19 `OPEN/NOT_STARTED/0/DRAFT`;
- AgentRun 96 `FAILED`, sin padre ni hijos retry;
- WS19: 4 turns, 2 AgentRuns, 2 attachments;
- cero AgentRuns, remote closes o fresh-session operations no terminales.

### WorkSession 19 y AX42

- remote session `6547081d-895e-4be1-a8fd-d115b7743cdf`;
- HEAD `e4287dbc...`;
- `AGENTS.md` blob `75173298...`, SHA-256 `a09adc58...`, limpio;
- un único path Android modificado y retenido, sin leer su contenido;
- admission `7a89d9e4...`, allocation `08db9255...`, registry
  `c867783c...`;
- journal `3c9f7884...`, 56 terminales, 0 no terminales;
- runner/adapter/installers `669f2f58...`, `e3d5402f...`, `0ca61d84...`,
  `8a23efc5...`;
- capacidad normal `2/4`, heavy `1/2`; slots `3/0/0/3`;
- rootful Docker/containerd inactivos/masked y socket ausente;
- backups/timers/RAID sanos.

### No impacto y recursos excluidos

- producción `53d4a7f4...`, preview `b097910a...`, Beautips `ff9d2a0a...`,
  Caddy `612f0ff4...`, health 200 y cero restarts;
- compose productivo `ec3e3e22...`;
- rutas Expo retiradas y activation network ausente;
- Beautips registry preexistente `87ba464a...` intacto;
- admission/allocation excluidos `5ced8132...` / `bd45cac9...` intactos.

Los flags legacy observados no se interpretan como política V2. En particular,
la existencia previa de routing/preview Beautips no autoriza un solo recurso o
capability V2 para ese proyecto.

## Conclusión de auditoría

No se encontró una divergencia que impida especificar V2. Sí se encontraron
deudas arquitectónicas reales que justifican los diez módulos y su orden:
control común, seguridad, cambio/rama, artefactos, validación, revisión,
integración, release, UI y resiliencia/onboarding.

La primera implementación no debe ser “hacer visible un botón de build”. Debe
ser M0 y M1, seguida del agregado de cambio y evidencia; sólo entonces M4 puede
resolver el build real de forma segura y reusable.
