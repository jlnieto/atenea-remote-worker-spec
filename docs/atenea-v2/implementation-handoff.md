# Handoff de implementación de Atenea V2

Este documento está dirigido al agente que implemente el programa después de
su aceptación. No es una autorización de ejecución.

## Punto de entrada

Primera tarea futura: `bootstrap-atenea-v2-control-contracts`, tarea `0.1`.

Antes de empezarla, el operador debe autorizar expresamente ese cambio y la
base Git exacta que resulte de revisar esta rama de planificación. No se debe
interpretar la autorización de planificación como autorización para escribir
código, migrar o desplegar.

## Orden obligatorio

1. `bootstrap-atenea-v2-control-contracts`
2. `harden-atenea-v2-privileged-actions`
3. `add-atenea-v2-development-change-control`
4. `add-atenea-v2-artifact-evidence`
5. `add-atenea-v2-protected-validation`
6. `add-atenea-v2-private-review`
7. `add-atenea-v2-reviewed-integration`
8. `add-atenea-v2-protected-release`
9. `unify-atenea-v2-operator-experience`
10. `prove-atenea-v2-resilience-and-onboarding`

No se implementan varios cambios en una misma rama ni se anticipan tareas de
un módulo dependiente. Si una implementación descubre que el diseño debe
cambiar, se actualiza y acepta primero el OpenSpec; no se introduce una
excepción silenciosa en código.

## Disciplina por tarea

Para cada checkbox de `tasks.md`:

1. auditar base y live state;
2. marcar conceptualmente sólo esa tarea como en curso;
3. implementar el mínimo cambio completo;
4. ejecutar pruebas finitas proporcionales al riesgo;
5. documentar evidencia sanitizada;
6. confirmar no impacto;
7. ejecutar `openspec validate <change> --type change --strict
   --no-interactive`;
8. ejecutar `git diff --check` para worktree e índice;
9. crear y verificar `SHA256SUMS` y calcular el SHA-256 de ese fichero;
10. marcar sólo esa tarea completa;
11. commit único y publicación fast-forward;
12. empezar la siguiente sólo cuando el commit remoto coincide.

Si aparece divergencia de Git, ownership, RAID, backup, runtime, producción,
recursos extranjeros o estado retenido, conservar evidencia sanitizada y
detenerse. No adoptar, reparar, liberar, eliminar ni reconstruir.

## Base de código

La auditoría de planificación determinó:

- programa lineal más completo: `90b4572c...` antes de esta rama;
- aplicación aceptada más completa: `39d7d737...`, que contiene `main`
  `e4287dbc...` y el slice de cierre remoto `918f3b2e...`;
- producción aún ejecuta la imagen construida desde `918f3b2e...`.

Eso no fija automáticamente la base de implementación. La tarea M0.0.1 debe
volver a consultar refs, comparar árboles y decidir mediante fast-forward o
una rama de integración explícita. No se mezcla código copiando archivos entre
checkouts y no se reescribe historia.

## Invariantes que no se negocian

- gates V2 globales y por proyecto en `false` por defecto;
- primer allowlist real: exactamente `atenea`;
- ningún enablement V2 para Beautips u otros proyectos;
- ninguna autoridad de Docker/runtime para AgentRun o cliente;
- backend productivo sin ejecución de comandos del manifest V2;
- no aceptar comandos, paths, slots, puertos, servicios, endpoints, labels,
  imágenes, credenciales ni recursos escogidos por el cliente;
- `AgentRun.SUCCEEDED` no equivale a validación;
- ningún 4xx determinista usa retry de transporte;
- toda mutación remota durable, idempotente, monotónica y reconciliable;
- no éxito sin persistir receipt exacto;
- rollback conserva estado y no reconstruye ownership liberado;
- timeouts finitos en red, procesos, navegador y reconciliación;
- logs/evidencia sin prompts, respuestas, contenido de adjuntos, secretos,
  auth, cookies, historial de Codex o dumps de entorno.

## Protección de WorkSession 19

Hasta una autorización H5 específica:

- no crear `DevelopmentChange` para WS19;
- no backfill de su FK;
- no prompt, retry ni AgentRun;
- no validación de su borrador;
- no iniciar preview/runtime;
- no publicar, mergear, cerrar ni liberar;
- no modificar registration, admission, allocation, registry, slot, worktree,
  turns, attachments, logs o artifacts.

Las pruebas de migración deben usar fixtures sintéticos que reproduzcan la
forma del legado sin copiar contenido real.

## Primera entrega funcional recomendada

El primer resultado visible útil llega al terminar M4, no antes:

- seleccionar un cambio Atenea sintético;
- ejecutar `ANDROID_BUILD` y la validación web definida;
- recuperar estados y artefactos tras restart;
- mostrar que Docker sigue ausente dentro de AgentRun;
- demostrar que backend y cliente tampoco eligen shell/paths;
- detenerse antes de publicar APK, abrir preview o enviar prompt.

Esto corrige la limitación real sin convertir el runner Codex en un contenedor
privilegiado.

## Reglas de UI

M8 y cualquier UI provisional anterior deben cumplir:

- estado entendible en menos de tres segundos;
- una acción primaria;
- bloqueo y siguiente acción visibles sin scroll;
- copy breve y accionable;
- datos/persistencia, DOM y visual comprobados por separado;
- Playwright real 1440x900 y 390x844;
- capturas finales sanitizadas;
- permisos, stale/offline, clipping, overflow y mensajes largos verificados.

Una build correcta, un health 200 o un assertion de base de datos no sustituyen
la validación visual.

## Evidencia y entrega de cada parada

El informe debe incluir:

- tareas completadas y primera pendiente;
- estado del cambio OpenSpec;
- ramas, commits, árboles y upstream por repositorio;
- pruebas y resultados;
- evidencia y SHA-256 de su `SHA256SUMS`;
- estado Git, servicios, slots, admission, ownership, backup y RAID;
- producción, preview, Beautips, routing y recursos excluidos;
- gates activos/inactivos;
- autorizaciones humanas pendientes;
- HEAD exacto para la siguiente revisión.

## Regla para archivar

Un cambio OpenSpec sólo se archiva cuando:

- todos sus tasks están realmente completados;
- strict validation pasa;
- rollout/rollback y observación exigidos están probados;
- evidencia final no-impact está sellada;
- la capacidad sigue deshabilitada o activada sólo dentro del gate aceptado;
- el operador ha tomado las decisiones humanas que el cambio declara.

“Código terminado” sin rollout aceptado o evidencia operativa no es motivo para
archivar.
