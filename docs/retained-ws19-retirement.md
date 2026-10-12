# Retirar el propietario WS19 retenido sin deshabilitar v4

La liberación legacy ordinaria conserva sus restricciones. El mediador reconoce
sólo el propietario retenido `6547081d-895e-4be1-a8fd-d115b7743cdf`, commit
`e4287dbc9a6a3545e6e1d0eda3b488e4a8e8edd5`, desde la configuración root-owned
reviewed de canonical `07fdf9f56333ff8002450d7bc2719ac4000fe4a7`.

Los fingerprints de configuración, workspace record, allocation y borrador se
declaran en el componente instalado. No hay nuevos parámetros de ruta, comando,
commit, permiso, symlink o flags para saltar ownership. El request de liberación
existente no cambia; la prueba especial se genera internamente en el preflight.

Sólo se retira el descriptor WS19 del registry. `selectionEnabled=false`,
`executionEnabled=true`, canonical commit, runner y demás campos se conservan.
Se liberan las admisiones mediante su operación normal, se renombra la allocation
con conservación de bytes/metadatos y se mantiene el journal idempotente por UUID.
El worktree, Git, borrador, conversación, adjuntos y artefactos no se borran.

Después de RELEASED, repetir la liberación exige que el estado conservado siga
siendo exacto. `--verify-retained-ws19` consulta sólo las raíces fijas y valida
journal sellado, todos los stages, recibo final, admisiones liberadas, allocation
retirada y borrador conservado. El installer exige esta prueba para reconocer la
configuración sin descriptor WS19; nunca la acepta sólo porque esté vacía.

Instalar estos componentes no ejecuta la retirada. App debe crear primero su
intent autorizado de abandono y consumir el recibo normal de liberación. No se
debe reactivar la configuración legacy ni modificar manualmente registros.

El installer del worker acepta como predecesor únicamente el liberador instalado
aa02b2a7… con su identidad root-owned exacta. Tras detener controladamente el
worker instala la nueva revisión; verify exige la nueva revisión, no acepta el
predecesor. Las reglas sudoers y el protocolo público permanecen sin cambios.
