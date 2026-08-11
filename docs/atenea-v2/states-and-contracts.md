# Estados y contratos de Atenea V2

## Modelo de dominio

### `DevelopmentChange`

Agregado duradero que representa un cambio independiente sobre un proyecto.

Identidad mínima:

- `id` interno y `changeKey` público no secuencial;
- `projectId` y `projectPolicyRevision`;
- `title` y descripción operativa breve, sin copiar el prompt;
- `baseRef`, `baseCommit`, `workspaceBranch` y `workspaceIdentity`;
- `selectedWorkerId` y `remoteSessionId` cuando corresponda;
- fingerprints de fuente actual y observación canónica;
- revisiones de cada proyección de estado;
- timestamps, creador y versión optimista.

Cardinalidades:

- `Project 1 → N DevelopmentChange`;
- `DevelopmentChange 1 → N WorkSession` secuenciales;
- sólo una WorkSession `OPEN` o `CLOSING` por cambio;
- varios cambios abiertos del mismo proyecto son válidos si sus ramas,
  worktrees y ownership son distintos.

### Recursos operativos

- `ValidationPlan`: conjunto inmutable de checks requerido para una fuente.
- `ValidationRun`: ejecución durable de un check simbólico.
- `Artifact`: blob inmutable identificado por SHA-256.
- `ArtifactManifest`: conjunto ordenado de artefactos y procedencia.
- `ReviewEnvironment`: runtime privado y temporal de una fuente.
- `ReviewDecision`: decisión humana ligada a fuente/evidencia exactas.
- `IntegrationOperation`: publish/PR/checks/merge/reconcile.
- `ReleaseCandidate`: commit integrado más manifests elegibles.
- `DeploymentPlan`: preflight inmutable y legible antes de confirmar.
- `DeploymentOperation`: promoción/rollback durable.
- `PrivilegedActionAuthorization`: step-up de un solo uso ligado a target.
- `AuditEvent`: hecho append-only sin contenido sensible.

## Proyecciones de estado de `DevelopmentChange`

No se persiste un “superestado” que intente codificar todas las combinaciones.
El backend deriva una fase de UI a partir de los ejes siguientes.

### Ciclo del cambio

```text
OPEN -> CLOSING -> COMPLETED
  \----------------> ABANDONED
```

- `OPEN`: admite trabajo y operaciones no terminales.
- `CLOSING`: integración/release o abandono están reconciliándose.
- `COMPLETED`: objetivo integrado y, si la política lo exige, desplegado.
- `ABANDONED`: decisión humana terminal; conserva todo lo retenido.

`COMPLETED` y `ABANDONED` son terminales. Reabrir crea un cambio sucesor y no
reescribe el historial.

### Fuente

```text
UNMATERIALIZED -> CLEAN <-> DIRTY
                     \-> STALE
                     \-> CONFLICTED
                     \-> RECONCILING -> CLEAN|DIRTY|CONFLICTED
```

- `UNMATERIALIZED`: no existe aún workspace propio demostrado.
- `CLEAN`: worktree e índice coinciden con la identidad registrada.
- `DIRTY`: hay borrador propio retenido y fingerprinted.
- `STALE`: la fuente canónica avanzó desde el base commit observado.
- `CONFLICTED`: no puede demostrarse reconciliación segura.
- `RECONCILING`: operación durable de actualización en curso.

Una transición de fingerprint invalida validación, revisión y elegibilidad de
release anteriores. Sus registros se conservan como `STALE`.

### Ejecución de edición

```text
IDLE -> QUEUED -> STARTING -> RUNNING -> IDLE
                    |           |
                    +-> RECONCILING -> IDLE|BLOCKED
                    +-> CANCELLING -> IDLE|BLOCKED
```

Este eje se deriva de AgentRuns no terminales. No expresa calidad del código.

### Validación

```text
NOT_RUN -> QUEUED -> RUNNING -> PASSED
                         |----> FAILED
                         |----> BLOCKED
                         |----> CANCELLED
PASSED|FAILED|BLOCKED ----------> STALE   (si cambia un input)
STALE --------------------------> QUEUED  (nuevo plan)
```

`FAILED` significa que el check se ejecutó y encontró un defecto de la fuente.
`BLOCKED` significa que la política, definición, toolchain o precondición
impidió una validación significativa. `TRANSPORT` y `CAPACITY` se exponen como
causa operacional y no se convierten en falsos fallos de código.

### Revisión

```text
NOT_READY -> READY -> ACCEPTED
                    -> CHANGES_REQUESTED
ACCEPTED|CHANGES_REQUESTED -> STALE (si cambia fuente/evidencia)
```

`READY` exige el conjunto de validación vigente que define la política del
proyecto. `ACCEPTED` requiere identidad del operador y fingerprint exacto.

### Integración

```text
NOT_REQUESTED -> PUBLISHING -> PR_OPEN -> CHECKS_PENDING -> MERGE_READY
                                      -> MERGE_BLOCKED
MERGE_READY -> MERGING -> MERGED -> RECONCILING -> INTEGRATED
                      \-> FAILED
```

La integración sólo avanza si fuente, validación y revisión siguen vigentes.
La desaparición de respuesta se resuelve inspeccionando GitHub y Git; nunca
creando otra PR o merge a ciegas.

### Release

```text
NOT_ELIGIBLE -> ELIGIBLE -> PLANNED -> AUTHORIZATION_REQUIRED
             -> DEPLOYING -> DEPLOYED
                          -> FAILED -> ROLLING_BACK -> ROLLED_BACK|BLOCKED
```

Este eje es una proyección de `ReleaseCandidate` y `DeploymentOperation`, no
una propiedad del AgentRun. `DEPLOYED` sólo se persiste tras health y receipt
exactos. Un rollback usa el predecesor sellado; nunca recompila fuente.

## Estado derivado para clientes

La respuesta de detalle V2 contiene como mínimo:

```json
{
  "phase": "VALIDATION_REQUIRED",
  "stateRevision": 17,
  "isStale": false,
  "blocking": null,
  "primaryAction": {
    "kind": "RUN_REQUIRED_VALIDATION",
    "label": "Validar cambio",
    "enabled": true,
    "requiresConfirmation": false,
    "requiresStepUp": false
  },
  "secondaryActions": [],
  "updatedAt": "2026-08-11T20:00:00Z"
}
```

Reglas:

- `phase` y acciones son server-owned;
- el cliente no compone permisos a partir de enums parciales;
- un snapshot offline muestra `isStale=true` y bloquea mutaciones;
- sólo hay una acción primaria por pantalla;
- un identificador o mensaje largo debe poder verse sin clipping u overflow.

## Contrato durable de operación

Toda mutación remota o con efecto significativo usa:

- `operationId`: UUID generado por Atenea o por el cliente sólo como
  idempotency key opaca, nunca como identidad de recurso;
- `idempotencyKey`: única por operador y tipo de operación;
- `requestFingerprintSha256`: canonicalización de target e inputs permitidos;
- `targetFingerprintSha256`: ownership y versión exacta del target;
- `state` y `revision` monótonos;
- `failureCategory`, `failureCode`, mensaje breve y `nextAction`;
- `receiptSha256` y timestamps terminales inmutables;
- actor, sesión autenticada y autorización privilegiada cuando aplique.

Invariantes:

1. misma key + mismo fingerprint devuelve la misma operación;
2. misma key + fingerprint distinto devuelve conflicto determinista;
3. una revisión nunca disminuye;
4. una identidad/receipt terminal no cambia;
5. antes de repetir un efecto incierto se inspecciona el sistema remoto;
6. éxito remoto se proyecta sólo después de persistir el receipt exacto;
7. rollback no reconstruye ownership ya liberado;
8. un recurso ambiguo o extranjero produce `OWNERSHIP` y cero mutaciones.

## Taxonomía de fallos

| Categoría | Significado | Respuesta operativa | Retry automático |
|---|---|---|---|
| `TRANSPORT` | timeout, conexión o respuesta no interpretable | entrar en reconciliación finita e inspeccionar por `operationId` | sólo bajo política acotada |
| `CAPACITY` | no hay slot/permit disponible | mantener cola durable o mostrar espera/cancelación | sí, sin crear operación duplicada |
| `VALIDATION` | input o código no cumple el contrato | terminar inmediatamente con resultado accionable | no |
| `POLICY` | operación, proyecto, rol o gate no autorizados | 4xx determinista y sin contactar al worker | no |
| `OWNERSHIP` | target/fingerprint/labels no demuestran pertenencia | bloquear, conservar evidencia y pedir intervención | nunca |

Ningún HTTP 4xx determinista recorre la ventana de “worker no disponible”. El
HTTP transporta el resultado, pero la categoría durable es la fuente de verdad.

## Contrato de source fingerprint

El fingerprint de fuente se calcula en el componente propietario del Git
workspace e incluye, como mínimo:

- repositorio y rol;
- base ref y base commit;
- workspace branch y HEAD;
- árboles de índice y worktree normalizados;
- conjunto ordenado de paths modificados, sin contenido;
- submódulos/LFS cuando el manifest los declare;
- revisión del manifest operativo y del bundle de instrucciones;
- identity/fingerprint de ownership.

No se considera equivalente un SHA de commit si existen cambios staged,
unstaged o untracked. El contenido de esos cambios no se copia a la evidencia
operativa.

## Contrato de validación

El cliente solicita una `ValidationCapability` cerrada. Ejemplos iniciales:

- `BACKEND_TEST`;
- `WEB_TEST`;
- `WEB_BUILD`;
- `ANDROID_TEST`;
- `ANDROID_BUILD`;
- `PLAYWRIGHT_ACCEPTANCE`;
- `CONTRACT_VALIDATION`;
- `SECURITY_AUDIT`.

Cada definición versionada posee:

- ID simbólico y `definitionRevision`;
- proyectos/perfiles allowlisted;
- imagen/toolchain por digest;
- mediador fijo y argumentos derivados por servidor;
- workload class y límites de CPU, memoria, disco y tiempo;
- red permitida y secretos nominales mínimos;
- artifact patterns fijos y límites;
- requisitos previos y política de cleanup.

El manifest del repo puede declarar qué definición necesita, pero no suministra
shell, path absoluto, host, puerto, socket, imagen, credencial ni target.

## Contrato de artefactos

Un `Artifact` incluye:

- `artifactId`, `sha256`, tamaño y MIME validado;
- clase (`APK`, `PACKAGE`, `TEST_REPORT`, `SCREENSHOT`, `TRACE`, `LOG_EXCERPT`,
  `SBOM`, `MANIFEST`);
- productor, source fingerprint, toolchain digest y timestamps;
- storage identity server-owned;
- retention class y fecha mínima de retención;
- estado de sanitización y visibilidad;
- firma/procedencia cuando aplique.

Un `ArtifactManifest` ordena artefactos y se identifica por su propio SHA-256.
La descarga verifica digest; la UI nunca recibe un path del worker.

Un APK de validación no es automáticamente un APK publicable. Firma y
publicación pertenecen a un canal protegido y a un artefacto derivado con
provenance propia.

## Contrato de revisión visual

Para cambios visibles:

1. verificar datos/persistencia;
2. verificar DOM/contenido y acciones;
3. inspeccionar resultado visual real;
4. ejecutar Playwright en `1440x900` y `390x844` con timeouts finitos;
5. comprobar jerarquía, estado en primer viewport, acción primaria, permisos,
   clipping, overflow y mensajes/identificadores largos;
6. retener capturas sanitizadas como artefactos del source fingerprint.

El preview sólo es accesible por ruta privada generada por el servidor. El
cliente no suministra puerto ni hostname.

## Contrato de integración

Un `IntegrationOperation` fija:

- change, repositorio, rama, base y commit esperado;
- source fingerprint;
- validation projection y review decision;
- PR esperada o por crear;
- estrategia de merge registrada;
- checks obligatorios;
- operación GitHub idempotente y receipt.

Publicar no implica mergear. Mergear requiere confirmación y, según política,
step-up. Tras merge se sincroniza el commit canónico y se ejecuta el cierre
remoto existente sin liberar estado retenido por política.

## Contrato de release

Un `ReleaseCandidate` sólo se crea a partir de:

- commit integrado exacto;
- validación vigente exigida por el target;
- review aceptada;
- artifact manifest elegible;
- SBOM/provenance cuando la política lo exija.

Un `DeploymentPlan` es read-only e incluye target fijo, versión actual,
candidato, preflight, health checks, predecesor y rollback. Confirmarlo consume
una `PrivilegedActionAuthorization` ligada a su SHA-256.

El executor de producción:

- acepta únicamente plan ID y autorización;
- resuelve credenciales/host/servicio internamente;
- no ejecuta shell del cliente ni del repo;
- persiste cada paso y receipt;
- aplica rollback automático sólo al predecesor sellado y autorizado por la
  política;
- conserva logs y artefactos sanitizados.

## Retención, backup y privacidad

Se conservan por política:

- Git mirror, worktrees y estado de índice;
- WorkSessions, turns y AgentRuns;
- attachments, artifacts, manifests y evidencias;
- operations, events, approvals y receipts;
- backups y volúmenes retenidos.

El teardown sólo retira recursos efímeros propios demostrados. La expiración de
un preview no elimina capturas ni decisiones. La desactivación de una feature
no borra schema ni registros.

Los backups V2 deben incluir nuevos metadatos y blobs según su clase, y cada
módulo debe demostrar restore en una ruta/host aislado antes de ampliar el
allowlist.

## Compatibilidad y migraciones

Orden obligatorio:

1. `expand`: tablas/columnas nullable, índices y readers tolerantes;
2. código dual-read/dual-write deshabilitado;
3. backfill sólo de datos no ambiguos y no retenidos especialmente;
4. activación únicamente para nuevos cambios Atenea;
5. observación y restore;
6. `contract` sólo con evidencia de que no existen consumidores legacy.

WorkSession 19 queda fuera de todo backfill y de toda activación. Su posible
vinculación futura no puede ser un script SQL: debe ser una operación de
dominio confirmada, idempotente y con preflight exacto.
