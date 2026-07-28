<!-- Phase 11, M5 — PR template. Keep the checklist honest; CI enforces most of it. -->

## Summary

<!-- What does this change do and why? Link the issue/ticket. -->

Closes #

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking, additive)
- [ ] Refactor (internal only, public API unchanged)
- [ ] Infrastructure / CI / docs
- [ ] Breaking change (requires a major version bump + migration notes)

## Backward compatibility

- [ ] No existing public API changed (paths, request/response shapes, status codes)
- [ ] No existing feature removed or simplified
- [ ] Database migration is additive and reversible (`upgrade`/`downgrade` both tested)
- [ ] Test coverage was not reduced

## Testing

<!-- How was this verified? Paste key test output or describe manual verification. -->

- [ ] `pytest backend/tests` passes locally
- [ ] `ruff check backend` passes
- [ ] New/changed code has tests

## Security & data

- [ ] No secrets committed
- [ ] PII handling reviewed (masking / retention / access control) where applicable
- [ ] AuthZ/authN considered for new endpoints

## Deployment notes

<!-- Migrations to run, config/secrets to add, feature flags, rollback plan. -->
