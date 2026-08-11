# Plan de entrega de Atenea V2

## Política de ejecución

El programa se implementa por OpenSpec, una tarea cada vez. Una tarea sólo se
considera completa cuando está implementada, probada, documentada,
strict-validada, commiteada y publicada. La tarea siguiente no empieza antes.

Cada módulo mantiene tres estados independientes:

- especificación: `DRAFT | SPECIFIED | ACCEPTED`;
- implementación: `NOT_STARTED | IN_PROGRESS | COMPLETE | BLOCKED`;
- activación: `DISABLED | SHADOW | ATENEA_CANARY | ATENEA_ENABLED | ROLLED_BACK`.

En esta planificación, los diez módulos están `SPECIFIED / NOT_STARTED /
DISABLED`.

## Grafo de dependencias

```text
M0 Control contracts
 ├─> M1 Privileged security
 └─> M2 Development changes <─ M1
       └─> M3 Artifact evidence
             └─> M4 Protected validation <─ M1/M2
                   └─> M5 Private review <─ M3
                         └─> M6 Reviewed integration <─ M1/M2/M4
                               └─> M7 Protected release <─ M1/M3/M4/M5
                                     └─> M8 Unified operator UX
                                           └─> M9 Resilience/onboarding
```

Las dependencias permiten separar contratos y pruebas. Para el primer rollout
se usa orden lineal M0–M9 para mantener una única tarea y una única superficie
de riesgo en curso.

## M0 — Control contracts

Objetivo: establecer el vocabulario y los límites transversales antes de crear
recursos V2.

Entregables:

- gates globales y políticas por proyecto, ambos deny-by-default;
- taxonomía común de fallos;
- envelope durable e idempotencia;
- `nextAction` server-owned;
- eventos de auditoría sanitizados;
- APIs V2 aditivas y compatibilidad legacy.

Aceptación:

- todos los endpoints V2 fallan cerrados con gates apagados;
- un 4xx determinista no invoca worker ni circuito de indisponibilidad;
- request key reutilizada con payload distinto se rechaza;
- reinicio conserva operación y revisiones;
- producción sigue comportándose como antes con schema expandido.

## M1 — Privileged action security

Objetivo: proteger la única cuenta sin convertir su rol administrador en una
autorización permanente para toda acción.

Entregables:

- passkey/WebAuthn;
- TOTP/códigos de recuperación controlados;
- familias de refresh rotatorias con detección de replay;
- lista/revocación de sesiones y versión de credenciales/rol;
- step-up y autorización de un solo uso por target;
- rate limiting y auditoría de autenticación.

Aceptación:

- robar sólo un access/refresh token no permite una acción privilegiada;
- replay de refresh revoca la familia;
- cambio de factor/rol invalida tokens previos;
- un step-up para target A no sirve para target B;
- recuperar acceso no desactiva auditoría ni genera bypass global.

## M2 — Development change control

Objetivo: permitir varias ramas independientes del mismo proyecto de forma
segura y comprensible.

Entregables:

- `DevelopmentChange` y vínculo opcional de WorkSession;
- creación de rama/worktree con fuente exacta;
- unicidad por cambio, no por proyecto;
- detección de drift/conflicto y reconciliación durable;
- listado y selección de cambios;
- operación futura de binding legacy, deshabilitada.

Aceptación:

- dos cambios Atenea pueden estar abiertos en ramas y worktrees distintos;
- una WorkSession/AgentRun no cruza de cambio;
- branch collision, fuente avanzada y ownership ambiguo bloquean sin mutar;
- cerrar una WorkSession no destruye el cambio ni su evidencia;
- WS19 permanece byte-exacta y sin binding.

## M3 — Artifact and evidence plane

Objetivo: almacenar outputs reproducibles sin tratarlos como archivos
arbitrarios del worker.

Entregables:

- catálogo `Artifact` y `ArtifactManifest`;
- upload/register/finalize por productor autorizado;
- verificación de digest y límites;
- procedencia, retención, sanitización y descarga mediada;
- backup/restore y garbage collection ownership-safe.

Aceptación:

- digest incorrecto, tipo no permitido o ownership cruzado se rechaza;
- un manifest es inmutable y reintentar finalize devuelve el mismo receipt;
- teardown de runtime no borra evidencia retenida;
- un path elegido por el cliente nunca se abre;
- restore reproduce metadata y bytes exactos en aislamiento.

## M4 — Protected validation

Objetivo: ejecutar validación real sobre la fuente exacta sin dar Docker a
Codex ni al backend productivo.

Entregables:

- `ValidationPlan`, `ValidationRun` y checks cerrados;
- broker AX42 rootless con toolchains por digest;
- backend/web/Android/Playwright;
- cola, permits heavy, cancelación y reconciliación;
- artifact manifests y staleness automática.

Primer canary funcional:

- build Android de Atenea y validaciones web aplicables sobre un cambio
  sintético o explícitamente autorizado;
- no publicación de APK, no prompt y no runtime productivo.

Aceptación:

- build pasa dentro del broker aunque Docker siga ausente del AgentRun;
- reboot/timeout/pérdida de respuesta no duplica el build;
- source fingerprint nuevo invalida el verde anterior;
- política/ownership 4xx terminan inmediatamente;
- capacidad llena se diferencia de caída del worker.

## M5 — Private review

Objetivo: mostrar el resultado real y recoger aceptación exacta.

Entregables:

- `ReviewEnvironment` con lease privado;
- URL/túnel server-owned;
- evidencia de datos, DOM y visual;
- viewports 1440x900 y 390x844;
- `ReviewDecision` aceptada/cambios solicitados;
- teardown y reconciliación.

Aceptación:

- Internet no puede alcanzar el preview;
- Android y web abren el mismo preview autorizado;
- capturas y DOM pertenecen al cambio/fingerprint correcto;
- cambiar un byte invalida aceptación;
- expiración conserva evidencia y no toca otros runtimes.

## M6 — Reviewed integration

Objetivo: llevar un cambio aceptado a GitHub sin ambigüedad.

Entregables:

- publish y PR durable por `DevelopmentChange`;
- checks requeridos y merge readiness;
- confirmación/step-up según política;
- merge y reconciliación idempotentes;
- cierre remoto de WorkSession mediante contratos actuales.

Aceptación:

- no se publica source stale o sin validación/review vigente;
- retry tras pérdida de respuesta no crea otra PR ni otro merge;
- branch/base/PR mismatch bloquea como ownership/validation;
- cierre no llega a `CLOSED` sin Git y receipt `RELEASED` persistidos;
- otros cambios del proyecto permanecen intactos.

## M7 — Protected release

Objetivo: desplegar artefactos revisados desde una frontera productiva mínima.

Entregables:

- `ReleaseCandidate`, `DeploymentPlan` y `DeploymentOperation`;
- target/service registry fijo;
- autorización step-up ligada al plan;
- executor con credenciales mínimas;
- preflight, health, receipt y rollback exacto.

Aceptación:

- código no integrado, artefacto mutable o autorización stale no despliega;
- AgentRun y broker de validación no alcanzan credenciales productivas;
- caída después de aplicar se reconcilia sin segundo deploy;
- health fallido activa sólo el rollback sellado;
- rollback conserva evidencia y nunca reconstruye fuente.

## M8 — Unified operator experience

Objetivo: hacer que móvil y web expliquen el estado y siguiente paso en menos
de tres segundos.

Entregables:

- navegación Proyecto → Cambios → Sesión/Validación/Revisión/Entrega;
- una acción primaria por pantalla;
- read models y commands compartidos;
- reconexión a operaciones durables;
- permisos/step-up visibles y accionables;
- accesibilidad y responsive.

Aceptación visual:

- datos/persistencia, DOM y resultado visual se prueban por separado;
- Playwright real en 1440x900 y 390x844;
- estado y CTA aparecen en el primer viewport;
- no hay clipping, overlap, overflow horizontal ni mensajes largos rotos;
- controles prohibidos no aparecen como acciones ejecutables;
- offline/stale no parece éxito.

## M9 — Resilience and onboarding

Objetivo: demostrar que V2 se recupera y puede ampliarse sin convertir Atenea
en un conjunto de excepciones por proyecto.

Entregables:

- matriz de fallos, SLO y alertas;
- restore completo de metadatos y artefactos;
- pruebas de cuatro slots/dos heavy;
- GC/retención ownership-safe;
- plantilla de onboarding por proyecto;
- plan de retirada posterior del executor legado.

Aceptación:

- backend/worker/reboot/partition/disk pressure tienen runbooks probados;
- restore en host/ruta aislados permite reconstruir el control plane sin
  tocar producción;
- orphan cleanup ignora recursos ambiguos/activos;
- el primer enablement real sigue siendo sólo `atenea`;
- Beautips y cada proyecto adicional permanecen deshabilitados hasta su
  OpenSpec y gate independientes.

## Estrategia de migraciones

Cada módulo con persistencia debe entregar:

1. inventario de constraints y datos existentes;
2. migración expand-only en el siguiente número Flyway libre;
3. prueba desde snapshot pre-migración y desde base vacía;
4. readers compatibles con null/legacy;
5. feature flags apagados;
6. backup y restore verificados;
7. candidato productivo sellado;
8. gate humano antes de aplicar migración;
9. observación antes de cualquier contract migration.

No se codifican ahora números futuros de migración: se asignan al empezar cada
módulo tras reauditar el HEAD real. No se ejecuta down-migration sobre
producción como rollback normal.

## Matriz mínima de pruebas

| Capa | Pruebas obligatorias |
|---|---|
| Dominio | transiciones válidas/inválidas, monotonicidad, staleness, next action |
| Persistencia | constraints, optimistic locking, idempotency, migration desde snapshot |
| API | auth, roles, step-up, 4xx deterministas, contratos Android/web |
| Worker | ownership, allowlist, rootless isolation, límites, timeouts |
| Integración | backend↔worker, GitHub simulado/real acotado, storage, outbox |
| Recuperación | pérdida de respuesta, restart backend, restart worker, partition, cancelación |
| Seguridad | replay, CSRF donde aplique, brute force, privilege escalation, path/command injection |
| UI | persistencia, DOM, visual, permisos, stale/offline, mensajes largos |
| Capacidad | cuatro normal, dos heavy, quinta petición, fairness y cancelación |
| Backup | backup/check/restore exacto con SHA-256 |
| No impacto | producción, preview, Beautips, routing, slots, RAID y recursos extranjeros |

Los tests no leen ni guardan contenido real. Los canaries usan datos sintéticos
salvo intervención humana explícita.

## Plantilla de rollout por tarea

1. Releer instrucciones, OpenSpec del módulo y contratos dependientes.
2. Verificar base Git local/remota, worktree e índice limpios.
3. Auditar en solo lectura Atenea y AX42; sellar fingerprints.
4. Implementar sólo la tarea actual con gates apagados.
5. Ejecutar suites finitas y checks de privacidad/autoridad.
6. Para UI, completar datos + DOM + visual desktop/mobile.
7. Strict-validar el cambio OpenSpec.
8. Crear `SHA256SUMS` y sellar su SHA-256.
9. Confirmar no impacto en WS19, producción, preview, Beautips y extranjeros.
10. Commit y push de la tarea.
11. Si la tarea siguiente cruza una puerta humana, detenerse.

## Plantilla de rollout de activación

Toda activación usa etapas separadas:

1. schema/código compatible con flags apagados;
2. shadow read-only;
3. canary sintético Atenea;
4. canary real sólo por acción explícita del operador;
5. observación definida;
6. enablement Atenea-only;
7. archivo OpenSpec sólo tras evidencia final.

No se habilita una cohorte global. Los allowlists V2 no aceptan wildcards,
aliases de cliente ni herencia de flags legacy.

## Plantilla de rollback

Orden:

1. deshabilitar allowlist de proyecto;
2. deshabilitar gate global;
3. detener nuevas operaciones y reconciliar las ya durables;
4. restaurar binario/imagen predecesora por digest;
5. verificar servicios, health, ownership, slots, backups y RAID;
6. conservar schema expandido y toda evidencia;
7. retirar sólo staging efímero exacto;
8. no liberar ni reconstruir ownership fuera del receipt de la operación.

El rollback automático sólo está permitido si el manifiesto sellado define el
predecesor exacto y la autorización del rollout lo incluye.

## Puertas humanas

| Gate | Momento | Autorización mínima |
|---|---|---|
| H0 | aceptar programa/módulo | cambio OpenSpec y base exacta |
| H1 | migración productiva | versión, backup, SQL/migration hash y rollback |
| H2 | instalación AX42 | bundle, hashes, servicios que reinicia y staging exacto |
| H3 | activar shadow/canary | flags exactos y allowlist `atenea` |
| H4 | prompt/AgentRun real | WorkSession/cambio exactos y límites de contenido |
| H5 | vincular estado legacy | plan `LEGACY_BIND`, ownership y fingerprint exactos |
| H6 | aceptar revisión | change/source/validation/artifact manifest exactos |
| H7 | publicar o mergear | PR/branch/base/checks y operación exactos |
| H8 | firmar/publicar APK | artefacto, certificado/canal y versión exactos |
| H9 | desplegar producción | DeploymentPlan hash, target, candidato y predecesor |
| H10 | rollback manual | operación fallida, predecesor y recursos afectados |
| H11 | enrolar/recuperar MFA | factor, dispositivo y política de recuperación |
| H12 | habilitar otro proyecto | OpenSpec de onboarding y allowlist exacto |

Una autorización de un gate no autoriza el siguiente. Una frase amplia no
sustituye fingerprints/targets cuando el sistema ya puede producir un plan
sellado.

## Criterio de finalización del programa

Atenea V2 sólo estará lista para uso general cuando:

- se pueda trabajar en al menos dos ramas Atenea concurrentes sin cruce;
- Android y web muestren el mismo estado durable;
- build Android, backend, web y Playwright sean reproducibles en AX42;
- review e integración invaliden resultados stale;
- un release Atenea no productivo y uno productivo autorizado demuestren
  idempotencia y rollback;
- passkey/step-up y revocación de sesiones estén operativos;
- restart/partition/restore/capacidad/GC hayan pasado;
- ninguna capacidad V2 esté habilitada para Beautips u otro proyecto sin su
  aceptación separada;
- el operador acepte explícitamente la transición de canary a uso real.
