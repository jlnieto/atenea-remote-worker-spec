# Programa maestro Atenea V2

Estado documental: `SPECIFIED / IMPLEMENTATION_NOT_STARTED / DISABLED`

Fecha de la auditoría de partida: 2026-08-11.

Este documento define el programa que convierte Atenea en una plataforma de
desarrollo remoto completa, operable desde Android o web, sin conceder a
Codex, al cliente ni al backend productivo autoridad directa sobre runtimes,
Docker, repositorios arbitrarios o producción.

La creación de este programa es exclusivamente documental. No autoriza
implementación, migraciones, despliegues, prompts, AgentRuns, runtimes,
previews, APK, cambios en AX42, operaciones Beautips ni activación de ninguna
capacidad V2.

## Resultado que persigue V2

Desde cualquier cliente autorizado, el operador podrá:

1. crear varios cambios independientes sobre ramas distintas del mismo
   proyecto;
2. trabajar con Codex dentro del cambio correcto;
3. ejecutar builds, tests y Playwright en un plano protegido;
4. revisar artefactos y previews privados vinculados al código exacto;
5. aceptar o pedir cambios sin confundir “Codex terminó” con “el cambio está
   validado”;
6. publicar, revisar e integrar el cambio mediante Git;
7. construir un candidato de release inmutable;
8. desplegarlo mediante una operación privilegiada separada, confirmada y con
   rollback verificable.

La unidad duradera de producto será `DevelopmentChange`. Una `WorkSession`
seguirá siendo la conversación y contexto de ejecución de un cambio, y un
`AgentRun` seguirá siendo una ejecución concreta de Codex. Ninguna de esas dos
unidades representará por sí sola validación, aceptación, integración o
despliegue.

## Autoridad documental

Para V2 se aplica este orden:

1. OpenSpecs canónicos ya archivados para seguridad, ownership, continuidad,
   runtime, adjuntos, previews, backup y cierre remoto;
2. los diez cambios OpenSpec V2 activos enumerados en este documento;
3. este programa maestro y sus decisiones de arquitectura;
4. código, tests y migraciones del candidato real durante cada implementación;
5. documentos históricos únicamente como evidencia de evolución.

Los documentos `docs/roadmap.md`, `docs/mobile-server-operations.md` y otros
textos anteriores contienen afirmaciones de estado que ya no siempre reflejan
el runtime actual. No se eliminan porque son historia útil, pero no deben usarse
para inferir qué está activo sin contrastar código, tests, migraciones y estado
real.

## Auditoría de partida

La auditoría se realizó en modo de solo lectura y sin inspeccionar prompts,
respuestas, adjuntos, credenciales, tokens, cookies, historial interno de Codex
ni dumps de entorno.

| Área | Estado observado |
|---|---|
| Programa local | Rama `codex/fix-reviewed-instruction-sandbox-cleanliness-20260811`, commit `90b4572c7e0fc38b3c8addfee241033858ea54e8`, árbol limpio y ref remota exacta antes de crear esta rama documental |
| Checkout de control | Rama de cierre remoto limpia en `ae225688dae8e816a4795fc2dcd1bb6bdb724c95`, árbol `b20280fdde9ee39df20e938830ea6f9050a7d3a0` |
| Fuente de aplicación aceptada más completa | `39d7d7379423b3da36ce89cc3329cbc6f87f00b3`, descendiente de `main` `e4287dbc...` y del cierre remoto `918f3b2e...`; limpia y publicada |
| Persistencia productiva | Flyway V66; WorkSessions 16 y 17 `CLOSED/RELEASED`; WorkSession 19 `OPEN/NOT_STARTED`; cero operaciones no terminales |
| WorkSession 19 | Cuatro turns, dos AgentRuns terminados con éxito y dos adjuntos; mismos registration, admission, allocation y remote session; no se leyó contenido |
| Fuente retenida de WS19 | HEAD `e4287dbc...`, `AGENTS.md` exacto y limpio; un único archivo de UI modificado por el canary aceptado |
| Worker | Journal exacto con 56 ejecuciones terminales y cero no terminales; runner e instaladores exactos |
| Capacidad | Admission `2/4` normal y `1/2` heavy; slots `3/0/0/3` |
| Servicios | Worker, adjuntos, preview, materialización y proxies sanos; rootful Docker/containerd inactivos y socket ausente |
| Datos y continuidad | Backups, comprobación de backup, health timers y RAID md0/md1/md2 sanos |
| Producción | Imagen `sha256:53d4a7f4...`; compose exacto `ec3e3e22...`; health 200; cero reinicios |
| Preview y Beautips | Imágenes preexistentes exactas, health 200 y cero reinicios; no se modificaron ni se incorporan a V2 |
| Routing legado retirado | Rutas `ateneaapp.yudri.es` y `ateneaapptest.yudri.es` ausentes; `atenea-activation-code_default` ausente y no debe recrearse |
| Identidad | Una cuenta activa `PLATFORM_ADMINISTRATOR`; ocho refresh sessions vigentes. Es una observación para el módulo de seguridad, no autorización para revocarlas |

El entorno conserva flags y recursos anteriores, incluidos recursos Beautips y
un allocation expresamente excluido. Los gates V2 empiezan siempre en `false`
y no heredan ni adoptan esos recursos. Cualquier divergencia futura respecto
de esta línea base bloquea la tarea que la detecte.

## Topología objetivo

```text
Android / Web
      |
      v
Atenea Control Plane
  identidad + step-up + políticas + estado durable + auditoría
      |
      +--> Change control ----> Git/GitHub canónico
      |
      +--> Validation broker --> AX42 rootless slots
      |                           build/test/browser only
      |
      +--> Review service -----> preview privado + artefactos
      |
      +--> Integration service -> PR/checks/merge reconciliado
      |
      +--> Release service -----> executor productivo restringido
                                  artefacto exacto, health y rollback

Codex AgentRun ----------------> sólo edición dentro del workspace propio
```

Los clientes sólo envían intención y referencias públicas de dominio. Atenea
resuelve en servidor comandos, rutas, slots, puertos, imágenes, endpoints,
labels, credenciales y targets desde registros allowlisted. Codex nunca recibe
la autoridad del broker de validación ni del executor productivo.

## Módulos OpenSpec

| Orden | Cambio OpenSpec | Resultado independiente | Dependencias | Estado |
|---:|---|---|---|---|
| M0 | `bootstrap-atenea-v2-control-contracts` | contratos transversales, gates, taxonomía, idempotencia y auditoría | ninguna | especificado, no iniciado |
| M1 | `harden-atenea-v2-privileged-actions` | passkeys/MFA, sesiones rotatorias y step-up ligado a la acción | M0 | especificado, no iniciado |
| M2 | `add-atenea-v2-development-change-control` | `DevelopmentChange`, varias ramas y WorkSessions por cambio | M0, M1 | especificado, no iniciado |
| M3 | `add-atenea-v2-artifact-evidence` | artefactos y manifiestos inmutables con procedencia y retención | M0, M2 | especificado, no iniciado |
| M4 | `add-atenea-v2-protected-validation` | builds/tests/Playwright en AX42 sin Docker para Codex/backend | M0–M3 | especificado, no iniciado |
| M5 | `add-atenea-v2-private-review` | previews privados y aceptación exacta del cambio | M1–M4 | especificado, no iniciado |
| M6 | `add-atenea-v2-reviewed-integration` | publicación, PR, checks, merge y reconciliación durables | M1–M5 | especificado, no iniciado |
| M7 | `add-atenea-v2-protected-release` | candidato, despliegue y rollback privilegiados | M1, M3–M6 | especificado, no iniciado |
| M8 | `unify-atenea-v2-operator-experience` | experiencia coherente en web y Android basada en `nextAction` | M0–M7 | especificado, no iniciado |
| M9 | `prove-atenea-v2-resilience-and-onboarding` | caos, restore, SLO y onboarding proyecto a proyecto | M0–M8 | especificado, no iniciado |

La dependencia es un DAG contractual. Por seguridad operativa, la primera
implementación debe ejecutarse secuencialmente M0 → M9, una sola tarea activa,
aunque una futura etapa pueda demostrar que dos módulos ya desacoplados se
pueden mantener en paralelo.

## Separación de responsabilidades

| Recurso | Responsabilidad | No representa |
|---|---|---|
| `Project` | repositorio y política operable | un cambio concreto |
| `DevelopmentChange` | objetivo, rama y ciclo de entrega duradero | una conversación o proceso Codex |
| `WorkSession` | contexto conversacional y workspace de un cambio | aceptación o release |
| `SessionTurn` | mensaje visible dentro de una sesión | comando de sistema arbitrario |
| `AgentRun` | proceso Codex de edición | build aprobado, revisión o despliegue |
| `ValidationRun` | ejecución protegida sobre una fuente exacta | aceptación humana |
| `ArtifactManifest` | salida inmutable y verificable | permiso para publicar/desplegar |
| `ReviewDecision` | decisión humana sobre fuente y evidencia exactas | merge o despliegue |
| `IntegrationOperation` | publicación/PR/merge reconciliados | operación productiva |
| `ReleaseCandidate` | commit integrado y artefactos elegibles | despliegue ya realizado |
| `DeploymentOperation` | promoción productiva confirmada | una instrucción a Codex |

## Primer flujo vertical útil

Después de M0–M3, M4 debe demostrar primero el problema real que motivó V2:

1. seleccionar un `DevelopmentChange` de Atenea;
2. congelar su fingerprint de fuente;
3. ejecutar `ANDROID_BUILD` mediante el broker protegido de AX42;
4. registrar APK/reports como artefactos inmutables;
5. ejecutar las validaciones web aplicables, incluida Playwright;
6. devolver un estado y siguiente acción claros a web y Android;
7. no enviar ningún prompt ni iniciar un AgentRun durante esa validación.

Ese slice no publica APK ni despliega. Sólo demuestra que una edición puede ser
validada de forma real y reproducible sin dar Docker a Codex.

## Protección explícita de WorkSession 19

WorkSession 19 y su remote session
`6547081d-895e-4be1-a8fd-d115b7743cdf` son estado retenido previo a V2.

- no se backfillea automáticamente `DevelopmentChange`;
- no se mueve de rama, worktree, slot o worker;
- no se vuelve a ejecutar ningún AgentRun;
- no se leen ni copian prompts, respuestas o adjuntos;
- no se libera, adopta, repara, valida ni despliega su borrador;
- una futura vinculación exige una operación explícita `LEGACY_BIND`, plan
  inmutable, preflight de ownership y autorización humana separada.

La migración expand-only mantiene válidas las WorkSessions legacy sin
`development_change_id`. El constraint actual de una sesión abierta por
proyecto sólo se retira en una fase contract posterior, cuando no pueda
afectar sesiones legacy.

## Reglas globales de implementación

- Toda funcionalidad V2 nace deshabilitada globalmente y por proyecto.
- La primera activación real sólo puede allowlistar `atenea`.
- Beautips y cualquier otro proyecto requieren un OpenSpec y una autorización
  independientes.
- Todo efecto remoto usa operación durable, fingerprint de petición,
  idempotency key y revisiones monótonas.
- Un 4xx determinista de política, validación u ownership no entra en la
  ventana de indisponibilidad del worker.
- Ningún recurso extranjero o ambiguo se adopta, repara o elimina.
- Ningún cliente elige comandos, rutas, slots, puertos, servicios, endpoints,
  labels, imágenes o credenciales.
- Cada tarea conserva evidencia sanitizada y un `SHA256SUMS` sellado.
- Las migraciones son expand/contract; rollback desactiva y preserva antes de
  considerar una down-migration.
- La UI consume estados y `nextAction` derivados por servidor; no inventa
  disponibilidad ni permisos.

## Documentos del programa

- [Auditoría de partida](current-state-audit.md)
- [Decisiones de arquitectura](architecture-decisions.md)
- [Estados y contratos](states-and-contracts.md)
- [Plan de entrega, pruebas y rollout](delivery-plan.md)
- [Mapa OpenSpec legible por herramientas](openspec-map.yaml)
- [Handoff de implementación](implementation-handoff.md)

## Próximo paso autorizado necesario

Tras revisar y aceptar este plan, el siguiente permiso debe nombrar
exclusivamente `bootstrap-atenea-v2-control-contracts`, su base Git exacta y su
tarea `0.1`. Hasta recibirlo, todos los módulos permanecen especificados pero
no iniciados y todos los gates V2 permanecen inexistentes o deshabilitados.
