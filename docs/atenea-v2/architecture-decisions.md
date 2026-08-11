# Decisiones de arquitectura de Atenea V2

Estas decisiones son normativas para los OpenSpecs V2. Cambiarlas requiere una
propuesta explícita que enumere contratos afectados, migración, pruebas,
rollout, rollback y compatibilidad con estado retenido.

## ADR-001 — `DevelopmentChange` es la unidad de entrega

Decisión: introducir `DevelopmentChange` por encima de `WorkSession`.

Motivo: una conversación no es una rama, un build, una revisión ni un release.
El cambio debe sobrevivir al cierre o sustitución de una WorkSession y agrupar
la trazabilidad completa desde intención hasta producción.

Consecuencias:

- un proyecto puede tener varios cambios abiertos;
- cada cambio posee una rama exacta y puede tener varias WorkSessions
  secuenciales, pero sólo una `OPEN/CLOSING` a la vez;
- un AgentRun siempre pertenece a una WorkSession y, a través de ella, a un
  cambio;
- las WorkSessions legacy pueden permanecer temporalmente sin cambio asociado.

## ADR-002 — Estado compuesto, no una máquina monolítica

Decisión: representar el estado de un cambio mediante proyecciones ortogonales
de fuente, ejecución, validación, revisión, integración y release.

Motivo: un enum único produciría combinaciones falsas. Por ejemplo, una fuente
puede estar limpia pero con validación obsoleta, o una PR abierta puede tener
un preview expirado sin dejar de estar correctamente publicada.

Consecuencias:

- cada eje tiene transiciones monótonas propias;
- una mutación de fuente invalida explícitamente validación, revisión y
  elegibilidad de release;
- `phase`, `blockingReason` y `nextAction` son proyecciones derivadas en el
  servidor, no campos decididos por los clientes.

## ADR-003 — `AgentRun` sólo mide el proceso Codex

Decisión: `AgentRun.SUCCEEDED` significa únicamente que el proceso Codex
terminó correctamente y entregó su resultado técnico.

No significa:

- que el código compile;
- que los tests o Playwright pasen;
- que el operador acepte el resultado;
- que exista PR, merge o despliegue.

Motivo: el código vigente ya separó `process_outcome` de
`WorkSession.acceptance_state`; V2 completa esa separación con recursos
durables dedicados.

## ADR-004 — Validación en un broker protegido

Decisión: build, tests, runtime de desarrollo y navegador se ejecutan mediante
un broker de validación de AX42, separado tanto de Codex como del backend
productivo.

Motivo: el verificador heredado acepta comandos del manifest y el backend
histórico tuvo autoridad Docker. Dar el socket Docker a un AgentRun o mantener
esa autoridad amplia en producción rompe el límite de privilegios.

Consecuencias:

- el cliente selecciona una operación simbólica, nunca un comando;
- el servidor resuelve una definición versionada y allowlisted;
- el broker usa slots rootless y toolchains por digest;
- Codex puede solicitar validación, pero no recibe credenciales, sockets ni
  capacidad para ejecutarla directamente;
- producción no monta el socket Docker para el flujo V2.

## ADR-005 — Fuente exacta y resultados inmutables

Decisión: toda validación, revisión, integración y release se liga a un
`sourceFingerprint` exacto y a manifests SHA-256 inmutables.

Motivo: un resultado verde deja de ser válido cuando cambia cualquier byte
relevante, definición de validación, toolchain o dependencia sellada.

Consecuencias:

- no existe “último build” sin identidad;
- cualquier avance de fuente marca resultados previos `STALE` sin borrarlos;
- la deduplicación sólo reutiliza un resultado si coinciden todos los inputs;
- el despliegue selecciona un artefacto por digest, nunca recompila una rama
  mutable.

## ADR-006 — Artefactos y evidencia forman un subsistema propio

Decisión: capturas, reportes, trazas, APK, paquetes y manifests usan un
catálogo durable con ownership, procedencia, integridad y retención.

Motivo: los adjuntos conversacionales ya resuelven input/output de
WorkSession, pero un artefacto de validación o release necesita semántica y
retención diferentes.

Consecuencias:

- `WorkSessionAttachment` no se sobrecarga como release artifact;
- un artefacto puede enlazarse a WorkSession/AgentRun sin perder su productor
  canónico (`ValidationRun` o `ReleaseCandidate`);
- el storage nunca se expone como path elegido por el cliente;
- descargar se hace por un descriptor autorizado de Atenea.

## ADR-007 — Preview y aceptación son operaciones distintas

Decisión: `ReviewEnvironment` gestiona el runtime privado; `ReviewDecision`
persiste la decisión humana sobre una fuente y evidencia exactas.

Motivo: abrir una web no equivale a aceptarla, y apagar un preview no debe
perder la decisión ni las capturas retenidas.

Consecuencias:

- los previews tienen leases y teardown idempotente;
- la aceptación queda obsoleta si cambia la fuente o la proyección validada;
- UI visible se prueba por separado en datos/persistencia, DOM y resultado
  visual.

## ADR-008 — Integración y producción son planos separados

Decisión: publicar/mergear Git pertenece a `IntegrationOperation`; desplegar
pertenece a `DeploymentOperation`.

Motivo: un commit fusionado puede no ser desplegable y una release puede
promoverse varias veces sin volver a editar ni integrar código.

Consecuencias:

- el cierre de WorkSession conserva su contrato Git/release remoto actual;
- una integración sólo consume revisión y validación no obsoletas;
- una release sólo consume un commit integrado y artefactos elegibles;
- Codex ordinario no accede a ninguna credencial productiva.

## ADR-009 — Rol permanente más autorización efímera

Decisión: `PLATFORM_ADMINISTRATOR` es necesario pero no suficiente para una
acción de alto impacto. Producción, merge, rollback, recuperación sensible y
cambio de política requieren step-up reciente y una autorización de un solo
uso ligada al target exacto.

Motivo: que exista un único usuario aumenta el impacto de robo de sesión; no
elimina la necesidad de segunda prueba de presencia.

Consecuencias:

- passkey/WebAuthn es el factor recomendado;
- TOTP y códigos de recuperación sirven como rutas de recuperación
  controladas, no como bypass silencioso;
- la autorización incluye acción, objeto, fingerprint, expiración y consumo;
- repetir la misma operación usa idempotencia; cambiar el target exige nueva
  autorización.

## ADR-010 — Refresh tokens rotatorios por familia

Decisión: cada login crea una familia de sesión identificable. Cada refresh
rota el token; reutilizar uno consumido revoca la familia completa.

Motivo: los tokens actuales son one-shot pero la cuenta no dispone de una
vista robusta de dispositivos/familias ni de detección explícita de replay.

Consecuencias:

- access tokens llevan `sessionId`, versión de rol y versión de credenciales;
- cambiar rol, contraseña o factores invalida tokens emitidos anteriormente;
- el operador puede listar y revocar sesiones sin ver tokens;
- rate limiting y alertas se aplican a login, refresh y step-up.

## ADR-011 — El servidor posee todas las decisiones peligrosas

Decisión: comandos, paths, slots, puertos, imágenes, endpoints, labels,
credenciales, servicios y targets se resuelven desde catálogos versionados y
allowlisted del servidor.

Motivo: validar parcialmente un valor suministrado por el cliente no elimina
confused-deputy ni path/command injection.

Consecuencias:

- las APIs aceptan IDs de dominio y operaciones simbólicas cerradas;
- los manifests de repositorio se tratan como input no confiable y sólo pueden
  referenciar definiciones registradas;
- un valor desconocido falla como `POLICY` o `VALIDATION`, nunca se ejecuta.

## ADR-012 — Operaciones durables, idempotentes y reconciliables

Decisión: toda mutación remota crea primero un registro durable con
`operationId`, idempotency key, request fingerprint y revisión monotónica.

Motivo: móvil, backend, red y worker pueden reiniciarse después de aplicar el
efecto pero antes de entregar la respuesta.

Consecuencias:

- un retry con la misma identidad devuelve la misma operación/recibo;
- una misma key con fingerprint distinto se rechaza;
- la reconciliación inspecciona estado persistido; no repite ciegamente;
- los estados terminales no vuelven atrás;
- el receipt remoto exacto se persiste antes de proyectar éxito.

## ADR-013 — Taxonomía de fallos cerrada

Decisión: toda operación clasifica fallos como `TRANSPORT`, `CAPACITY`,
`VALIDATION`, `POLICY` u `OWNERSHIP`.

Motivo: reintentar un 403 o un conflicto de ownership como si el worker no
estuviera disponible causa esperas falsas y riesgo de mutación duplicada.

Consecuencias:

- sólo transporte entra en la ventana de indisponibilidad;
- capacidad se encola o devuelve capacidad de forma explícita;
- 4xx deterministas se proyectan inmediatamente;
- ownership nunca se “repara” de forma automática.

## ADR-014 — GitHub es canónico y las ramas son explícitas

Decisión: cada `DevelopmentChange` fija repositorio, base ref, base commit y
workspace branch. GitHub sigue siendo la fuente canónica de integración.

Motivo: permitir varias ramas requiere que la conversación activa no sea la
única identidad del trabajo.

Consecuencias:

- branch collision y branch drift son errores explícitos;
- un cambio puede rebasarse/reconciliarse sólo mediante una operación
  confirmada y fingerprinted;
- múltiples cambios del mismo proyecto no comparten worktree ni
  externalThreadId;
- la PR siempre corresponde a la rama registrada del cambio.

## ADR-015 — Migración expand/contract y coexistencia legacy

Decisión: V2 se añade junto al modelo actual y se activa sólo para nuevos
recursos allowlisted. No hay backfill automático.

Motivo: WorkSession 19 y recursos retenidos no deben cambiar para introducir
el nuevo modelo.

Consecuencias:

- las primeras migraciones sólo añaden tablas/columnas/índices;
- una operación separada y humana puede vincular un legado tras preflight;
- quitar el índice único “una sesión abierta por proyecto” es una fase
  contract posterior;
- rollback normal deshabilita gates y conserva el schema expandido.

## ADR-016 — Clientes como consolas, no orquestadores

Decisión: Android y web consumen el mismo read model y muestran estado,
bloqueo y una acción primaria derivada por el backend.

Motivo: si cada cliente infiere transiciones, permisos o siguiente acción, el
sistema diverge y las recuperaciones durables dejan de ser comprensibles.

Consecuencias:

- mutaciones usan command/confirm/resume con idempotencia;
- reconexión recupera la operación durable en vez de crear otra;
- offline puede mostrar el último snapshot como obsoleto, nunca inventar
  éxito;
- cualquier cambio visible se verifica en 1440x900 y 390x844, además de la
  comprobación nativa pertinente.

## ADR-017 — Privacidad por minimización

Decisión: el plano de control conserva metadatos y evidencia necesarios, no
contenido incidental del entorno de ejecución.

Nunca se recopilan como evidencia:

- `auth.json`, tokens, cookies o credenciales;
- dumps de entorno;
- historial interno de Codex;
- prompts/respuestas fuera del contrato de conversación autorizado;
- contenido de adjuntos salvo intervención explícita y acotada.

Los logs estructurados usan identificadores, estados, duraciones, digests,
conteos y códigos normalizados. Cualquier output técnico se sanitiza y limita
antes de persistirse.

## ADR-018 — Onboarding proyecto a proyecto

Decisión: la plataforma se prueba primero sólo con `atenea`. Cada otro
proyecto requiere su propio OpenSpec, manifest revisado, fixtures, amenazas,
rollout, rollback y gate humano.

Motivo: toolchains, datos, runtimes y targets productivos varían. Un allowlist
global convertiría una prueba satisfactoria en autorización implícita para
recursos no evaluados.

Consecuencias:

- Beautips no hereda activación V2 aunque existan flags o recursos legacy;
- ningún proyecto nuevo se habilita por nombre recibido del cliente;
- el retiro del executor legado sólo ocurre después de restore y observación
  aceptados para todos los proyectos habilitados.
