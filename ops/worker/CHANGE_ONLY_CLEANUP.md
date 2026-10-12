# Limpieza del modelo anterior: preflight de recursos

Estado: preflight read-only implementado; productor de backup/retirada/recibo
RELEASED **pendiente**. No instalar ni aplicar una limpieza incompleta.

El manifiesto `change-only-resource-manifest-v1.json` está fijado por SHA-256
en `change-only-resource-plan-v1.py`. Sólo existe `--plan`; no admite rutas,
hosts, comandos, identidades ni un manifiesto del llamante. No modifica Git,
contenedores, volúmenes, archivos, configuración ni inventarios Codex. No
emite el recibo que exige el purgador DB App.

La lista App revisada contiene 17 WorkSessions de pruebas, 5 cambios y 2
rescates. El UUID del Apache real está protegido. Los 25 roots AX42 se
clasifican por identidad/bytes: preservar Apache, candidatos de pruebas
correlacionados con PROD y 9 recursos no correlacionados. Estos últimos no
se reclasifican por antigüedad, proximidad o por ausencia en una sola DB.

Antes de ejecutar comandos Git de lectura se verifica el config del mirror y
el gitdir/commondir; no se ejecutan filtros, hooks o comandos del paquete. Se
inspeccionan los cinco motores Docker fijos (rootless del operador y cuatro
slots) sin mostrar Env ni secretos. Una consulta no disponible impide sacar
una conclusión de ausencia. Los registros no pueden ser symlinks/hardlinks.

## Evidencia read-only del 12 de octubre

- Worker: cero ejecuciones no terminales, configuración v4-only sin drift.
- Apache real: root, HEAD y cinco registros coinciden; no es un candidato.
- 14 roots correlacionados pueden pasar a la fase de respaldo; WS6 y WS19
  contienen cambios sin commit y requieren archivo completo, no sólo Git HEAD.
- WS4/Beautips: tres contenedores, una red y cuatro volúmenes aún presentes en
  el slot4. Son recursos del sandbox por sus etiquetas; no son los servicios
  humanos de Beautips. No se ha parado ni eliminado ninguno.
- Su worktree apunta a la rama `ax42-beautips-wip-preservation-2ac2a5fd`, HEAD
  `b2f798e0ae3dec1b43bbfe4189aeadddd6287db8`. No se borrará esa rama ni el repo
  canónico por interpretar la sesión antigua como una autorización de Git.
- Los roots no correlacionados incluyen dos volúmenes de sesiones Atenea.
  Queda cerrar la autoridad de sus identidades antes de retirar recursos.

El resultado es BLOCKED, `receiptEmitted=false`, `mutationsPerformed=false`.
READY_FOR_ARCHIVE, si algún día se cumplen las precondiciones, tampoco significa
RELEASED ni autoriza la purga App. No copiar este plan como si fuera un recibo.

## Siguiente unidad obligatoria

Cerrar la correlación de esos nueve recursos con sus autoridades/datos
efectivos; añadir el respaldo verificable de código sin commit y de datos del
sandbox WS4, preservando su rama WIP y los repositorios/servicios reales.
Implementar la retirada cerrada por esas identidades, barrera de mantenimiento,
estado durable/idempotente y comprobación posterior de ausencia. Sólo ese
productor podrá emitir `change-only-resource-cleanup-receipt-v1` para la DB App.
No crear una API genérica de borrado ni aceptar targets del móvil.

Validación: `python3 -B ops/worker/test-change-only-resource-plan-v1.py` (12
tests), schema Draft 2020-12 y `git diff --check`. Las pruebas no usan Docker
real ni recursos PROD; el smoke real ejecutó exclusivamente `--plan`.
