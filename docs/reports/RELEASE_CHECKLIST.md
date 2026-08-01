# Release Checklist

**Date:** 2026-08-01
**Target release:** v1.0

## Version tagging

- [ ] Confirm the target version number follows semantic versioning (v1.0.0).
- [ ] Verify the version string is consistent across backend, frontend, and API metadata.
- [ ] Create an annotated Git tag for the release commit.
- [ ] Confirm the tag points at the validated, fully tested commit.

## Changelog

- [ ] Update `CHANGELOG.md` with the release version and date (2026-08-01).
- [ ] Group entries by area (backend, frontend, security, operations).
- [ ] Note the migration head (`c3d4e5f6a7b8`) and any schema changes.
- [ ] Confirm no emoji or informal wording in changelog entries.

## Release notes

- [ ] Draft user-facing release notes summarising capabilities and route families.
- [ ] Document known limitations (frontend formatting backlog; production-config prerequisites).
- [ ] List the production-configuration prerequisites required before operation.
- [ ] Include upgrade and migration guidance.

## Artifact build

- [ ] Run the backend test suite and confirm 1,442 passing / 0 failing.
- [ ] Run `tsc --noEmit` and confirm PASS.
- [ ] Run `vite build` and confirm a successful production build.
- [ ] Build and tag container images for backend and frontend.
- [ ] Record artifact digests/checksums for traceability.
- [ ] Pin dependencies and confirm lockfiles are committed.

## Sign-off

- [ ] Engineering sign-off: tests, build, and static analysis clean.
- [ ] Security sign-off: posture and compliance reviewed.
- [ ] Operations sign-off: deployment and rollback plans validated.
- [ ] Release owner approves the tagged build for promotion.
