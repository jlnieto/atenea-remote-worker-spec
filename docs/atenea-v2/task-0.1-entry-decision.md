# Decisión de entrada de M0.0.1

Fecha de captura: 2026-08-11.

Esta decisión cierra exclusivamente la tarea `0.1` de
`bootstrap-atenea-v2-control-contracts`. No implementa contratos V2, no crea
una migración y no modifica runtime, datos ni recursos operativos.

## Base Git aceptada

La rama de planificación autorizada estaba limpia y sincronizada en:

- rama: `codex/plan-atenea-v2-program-20260811`;
- commit: `5c2a759d616624b6c92b384c56ba26d36f42fe76`;
- tree: `73d5fdc3018251b7a07dc6c6dc6685947a8f6f95`;
- upstream y remoto: el mismo commit.

La base de aplicación aceptada para la futura implementación es:

- repositorio de aplicación: `atenea:/srv/atenea/workspace/repos/internal/atenea`;
- rama publicada:
  `codex/add-android-worksession-image-attachments-atenea-20260811`;
- commit: `39d7d7379423b3da36ce89cc3329cbc6f87f00b3`;
- tree: `bc3d9c42c43b311b1eb88681088091998ec8c247`;
- upstream y remoto: el mismo commit.

`39d7d737...` contiene como ancestros tanto `main`
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5` como el slice de cierre remoto
`918f3b2edbe87ca98dbbdefbb6947c2b2a4e0f80`. Es por ello la fuente completa
aceptada; ni `main` ni el commit de la imagen productiva deben usarse como
base de implementación aislada.

La planificación y la aplicación no admiten fast-forward entre sí. Su ancestro
común es `7e8afa6c7039a70aea3b330234ddeabdcf2a6587` y la comparación observada es
de 577 commits exclusivos en la línea de planificación y 161 en la de
aplicación. Por tanto, la tarea `1.1` deberá empezar en una rama de integración
explícita creada desde `39d7d737...` e incorporar la rama publicada de M0 por
historia Git. No se copiarán archivos entre checkouts, no se reescribirá
historia y cualquier conflicto se resolverá de forma visible antes de añadir
código.

## Número de migración

La fuente aceptada contiene migraciones Flyway consecutivas hasta V66 y la
base productiva informa V66 como última migración exitosa. Se reserva `V67`
como siguiente número libre para M0.

Esta reserva no autoriza crear, aplicar ni desplegar V67. La tarea `1.2`
deberá revalidar que V67 continúa libre antes de escribirla; la aplicación en
producción seguirá requiriendo una puerta H1 separada con SQL y hashes exactos.

## Modelo de compatibilidad

1. M0 será aditivo y expand-only. Las tablas, índices y value objects V2 no
   reemplazarán estructuras legacy durante este cambio.
2. Los gates globales y por proyecto nacerán deshabilitados y en un namespace
   independiente. Ningún flag, alias o allowlist legacy concede política V2.
3. Los endpoints legacy, registros, receipts y clientes actuales deben seguir
   siendo legibles y conservar comportamiento con V2 deshabilitado.
4. No habrá backfill automático. En particular, WS19 no recibirá FK, policy,
   operación ni transición V2.
5. La imagen predecesora debe poder convivir con el schema expandido antes de
   cualquier rollout. El rollback normal deshabilita gates y restaura una
   imagen sellada; no ejecuta una down-migration destructiva.
6. Las APIs V2 aceptarán identidades de dominio y operaciones simbólicas
   cerradas. Android y web no seleccionarán comandos ni recursos internos.
7. Un `AgentRun.SUCCEEDED` seguirá describiendo sólo el proceso Codex y no se
   convertirá en validación, aceptación o elegibilidad de release.

## Threat model de M0

| Amenaza | Límite exigido por M0 | Prueba futura mínima |
|---|---|---|
| Activación accidental por flags legacy | Gate global y policy exacta de proyecto, ambos deny-by-default y versionados | Negativas sin policy, con alias y con wildcard |
| Reuso malicioso de idempotency key | Fingerprint canónico de request y target; colisión determinista sin efecto | Misma key con payload o target distinto |
| Pérdida de respuesta tras efecto remoto | Operación durable antes del efecto, revisión monótona y receipt inmutable | Retry devuelve la operación original sin repetir efecto |
| Cliente como confused deputy | Servidor posee paths, comandos, slots, puertos, servicios, endpoints, labels, imágenes y credenciales | Selector interno desconocido rechazado antes de persistencia/contacto remoto |
| Retry incorrecto de un 4xx | Taxonomía cerrada `TRANSPORT`, `CAPACITY`, `VALIDATION`, `POLICY`, `OWNERSHIP` | Policy/validation/ownership terminan sin ventana de indisponibilidad |
| Cruce de proyecto, sesión u ownership | Target fingerprint exacto y comprobaciones server-owned | Identidad o ownership cruzado falla cerrado y no se repara automáticamente |
| Escalada desde Codex o backend | Ninguna autoridad Docker/runtime/productiva para AgentRun o API de producto | Gates apagados no contactan AX42; ningún selector ejecutable en contrato público |
| Fuga por auditoría | Audit facts append-only con IDs, digests, estados, conteos y tiempos exclusivamente | Tests impiden prompts, respuestas, adjuntos, auth, cookies, secretos e historial Codex |
| Rollback incompatible | Schema expandido tolerado por readers y predecesor sellado antes de H1 | Migración desde snapshot, restart y restore con gates apagados |
| Drift entre plan y aplicación | Rama de integración explícita desde la base aceptada y comprobación remota antes de cada tarea | Detención ante SHA/tree/upstream divergente |

## Estado retenido y exclusiones

La evidencia de entrada confirma V66, cero AgentRuns no terminales y WS19 en
`OPEN / NOT_STARTED / DRAFT`, con cuatro turnos, dos AgentRuns terminales, dos
adjuntos no ligados a AgentRun y cero bindings a turn. Su registro remoto,
admission y allocation conservan los hashes aceptados. Su worktree permanece
en `e4287dbc...` con un único path Android previamente retenido y el
`AGENTS.md` aceptado.

Producción, preview, Beautips, Caddy, routing, servicios AX42, capacidad,
slots, backups, RAID y recursos extranjeros se observaron sin mutarlos. Los
detalles sanitizados y sus hashes se encuentran en
`docs/atenea-v2/evidence/task-0.1/`.

## Consecuencia para la siguiente tarea

La primera tarea pendiente será `1.1`, limitada a tests rojos del contrato
compartido. No queda autorizada por esta decisión. Antes de iniciarla se debe
reconstruir un prompt desde el estado Git remoto final de esta tarea y obtener
una autorización humana nueva.
