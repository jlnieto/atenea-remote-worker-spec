## Why

WorkSession attachments safely carry conversational inputs and retained
outputs, but builds, test reports, screenshots, traces, APKs and release
packages need immutable provenance, manifest and retention semantics. Treating
them as arbitrary worker paths would prevent trustworthy review and release.

## What Changes

- Add immutable `Artifact` and ordered `ArtifactManifest` resources.
- Bind artifacts to exact producer, DevelopmentChange and source fingerprint.
- Add mediated register/finalize/read flows with digest, size, MIME,
  sanitization and retention checks.
- Add backup/restore and ownership-safe retention/garbage collection.
- Keep release signing/publication separate from validation artifacts.

## Capabilities

### New Capabilities

- `atenea-v2-artifact-evidence`: Immutable artifact, provenance, retention and
  evidence catalog for V2.

### Modified Capabilities

None.

## Impact

- Future backend schema/API, AX42 storage mediator and later web/Android reads.
- Reuses existing attachment security principles without changing retained
  attachments.
- Depends on M0 and M2 and remains disabled until separately rolled out.
