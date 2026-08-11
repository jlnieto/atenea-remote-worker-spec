# Evidencia sanitizada de M0.0.1

Captura coordinada el 2026-08-11 entre `18:51:45-03:00` y
`23:51:50+02:00`.

Esta evidencia contiene exclusivamente metadatos Git, hashes, estados,
conteos y health checks. No se leyeron ni almacenaron prompts, respuestas,
contenido de adjuntos, credenciales, tokens, cookies, `auth.json`, historial
interno de Codex ni dumps de entorno.

Las consultas remotas usaron timeouts finitos. PostgreSQL se consultó dentro
de `BEGIN; SET TRANSACTION READ ONLY; ...; ROLLBACK`. Las comprobaciones de
AX42 y contenedores fueron de lectura; no se inició, detuvo, reinició,
habilitó, adoptó, reparó, liberó ni eliminó ningún recurso.

- `git-and-application.txt`: base autorizada, base de aplicación, divergencia
  y migraciones.
- `operational-state.txt`: estado productivo, WS19, AX42, ownership y no
  impacto.
- `SHA256SUMS`: hashes verificables de ambos ficheros y de este README.
