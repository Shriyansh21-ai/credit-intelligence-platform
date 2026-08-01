# Version Checklist

**Date:** 2026-08-01
**Target release:** v1.0

## Semantic versioning

- [ ] Release version follows semantic versioning (v1.0.0).
- [ ] Version increment reflects the nature of changes (major for v1.0).
- [ ] Version string is consistent across backend, frontend, and metadata.
- [ ] Git tag matches the released version.

## API versioning

- [ ] API version headers present on responses.
- [ ] Deprecation headers middleware confirmed for deprecated routes.
- [ ] OpenAPI spec generated with enrichment metadata (contact/license/tags).
- [ ] Route families namespaced consistently under `/api/<prefix>`.

## Migration head

- [ ] Migration head recorded as `c3d4e5f6a7b8`.
- [ ] Single head confirmed (no divergent branches); 22 migrations total.
- [ ] Up/down round-trip verified clean.
- [ ] Migration head noted in changelog and release notes.

## Dependency versions

- [ ] Backend versions pinned (27 packages) with a committed lockfile.
- [ ] Frontend versions pinned (53 runtime + 17 dev) with a committed lockfile.
- [ ] No unused top-level packages.
- [ ] Dependency versions recorded for the release.

## Documentation version alignment

- [ ] Documentation references the release version and date (2026-08-01).
- [ ] Reports under `docs/reports/` reflect the released build.
- [ ] Changelog and release notes align with the tag.
- [ ] No stale version references remain.

## Backward compatibility

- [ ] API conventions unchanged for existing consumers.
- [ ] Schema changes are additive/migration-managed with a downgrade path.
- [ ] Breaking changes, if any, documented with migration guidance.
- [ ] Backward compatibility confirmed against prior consumers.
