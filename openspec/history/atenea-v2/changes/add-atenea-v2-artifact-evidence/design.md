## Context

Validation and review need outputs that remain trustworthy after runtime
teardown. Existing WorkSessionAttachment ownership is session-centric; release
artifacts require producer/source/toolchain provenance and immutable manifests.

Dependencies: M0 control contracts and M2 DevelopmentChange.

## Goals / Non-Goals

**Goals:**

- Content-address artifacts and manifests.
- Prevent client-selected paths and cross-change access.
- Preserve provenance and evidence after runtime teardown.
- Support bounded retention, backup, restore and safe GC.
- Distinguish validation APK from signed/published APK.

**Non-Goals:**

- Execute builds or browser tests.
- Sign, publish or deploy an artifact.
- Replace conversational attachments.
- Inspect arbitrary artifact contents as operational evidence.

## Decisions

### 1. Immutable two-phase registration

An authorized producer creates an upload/registration intent for a declared
artifact class. The worker writes to a server-owned staging identity, computes
digest/size, validates type and atomically finalizes into content-addressed
storage. Repeating finalize returns the same artifact.

### 2. Manifest as first-class identity

An ordered canonical manifest references artifacts plus producer, source,
toolchain and definition revisions. Its canonical JSON SHA-256 is persisted
and immutable. Consumers select the manifest, not “latest files”.

### 3. Separate storage and public API identities

Worker paths never cross the API. Atenea authorizes artifact IDs and streams or
issues bounded internal descriptors. A client path, URL, MIME or digest claim
is never trusted without server verification.

### 4. Retention and GC by demonstrated ownership

Policy assigns retention class. GC may delete only expired, unreferenced,
exactly owned blobs after a dry-run plan and durable receipt. Ambiguous,
foreign, retained or in-use blobs are skipped.

### 5. Signing is derivation

An unsigned/test APK remains a validation artifact. A protected signing channel
creates a new artifact with certificate/channel provenance; it never mutates
the original bytes or silently marks them publishable.

## Risks / Trade-offs

- [Blob exists without committed metadata] -> staging expiry and reconciler
  keyed by operation identity.
- [Metadata exists but blob is lost] -> verify on read, alert, restore from
  backup; never claim ready.
- [Sensitive output enters artifacts] -> allowlisted classes/patterns,
  sanitization status, size/type limits and no automatic publication.
- [GC deletes shared content] -> reference counting plus exact ownership and
  dry-run evidence.

## Migration Plan

1. Add expand-only artifact/manifests/links and storage-operation schema.
2. Deploy disabled storage mediator and synthetic content tests.
3. Prove backup/check/restore and cleanup against isolated synthetic blobs.
4. Enable only synthetic Atenea producers, then the protected validation
   producer after M4 authorization.

Rollback disables new registrations/download affordances, reconciles staged
operations and retains all finalized artifacts and metadata.

## Open Questions

Long-term cold-storage tier is deferred; retention classes and export contract
must remain storage-provider neutral.
