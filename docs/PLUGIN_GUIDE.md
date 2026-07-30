# Plugin Guide (v1.0.0)

The Enterprise Plugin Marketplace (`/api/ent/marketplace`) provides a full plugin
lifecycle. It complements the Banking-OS marketplace from Phase 10.

## Lifecycle

```
publish (draft/submitted) → add versions → review (approve/reject)
   → publish approved → check compatibility → install
```

1. **Publish** — `POST /api/ent/marketplace/publish {key, name, version,
   category, permissions?, dependencies?, compatibility?, billing_model}`.
   Creates the plugin (`submitted`) and its first version.
2. **Version** — `POST .../versions {plugin_id, version, changelog?}`. Semantic
   versioning is enforced (new version must be greater than the latest).
3. **Review** — `POST .../review {version_id, approve}`. Approving moves the
   plugin to `approved`.
4. **Publish approved** — `POST .../{plugin_id}/publish` sets `published` and
   marks the plugin `healthy`.
5. **Compatibility** — `GET .../{plugin_id}/compatibility` checks the platform
   version against the plugin's `min/max_platform` and verifies dependencies are
   themselves published.
6. **Install** — `POST .../{plugin_id}/install` (published + compatible only);
   increments the install count.

## Manifest fields

| Field | Meaning |
|-------|---------|
| `key` | unique slug |
| `category` | integration / analytics / risk / reporting / workflow / data / security / ai |
| `permissions` | RBAC permissions the plugin requests |
| `dependencies` | other plugin keys that must be published |
| `compatibility` | `{min_platform, max_platform?}` (platform version is `1.0.0`) |
| `billing_model` | free / subscription / usage (billing readiness) |

## Analytics

`GET /api/ent/marketplace/analytics/summary` reports totals, published count,
counts by status/category, total installs, top-installed plugins and how many are
`revenue_ready` (non-free billing model).

## Health & governance

Published plugins carry a `health` status; installs and versions are tracked for
audit. Plugin permissions are declared up-front so an admin can review the RBAC
surface a plugin requests before approval.

## Best practices

- Keep `min_platform` accurate; bump on breaking platform changes.
- Declare least-privilege `permissions`.
- Use semantic versioning and a clear `changelog` per version.
- Test in a sandbox tenant before publishing to the organization.
