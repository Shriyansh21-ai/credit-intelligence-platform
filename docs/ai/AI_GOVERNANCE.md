# AI Governance (M12)

## Goal: every AI decision is reproducible

The governance registry (`aip_ai_assets` / `aip_ai_asset_events`) tracks every AI
asset — prompts, models, datasets, agents, workflows, RAG indexes, reports — with
a version, a content **checksum** and a **lineage** bundle, plus an immutable
event trail. From any decision you can walk back to the exact artifact that
produced it.

## Lifecycle state machine

```
registered → validated → approved → deployed → retired
```

`transition(asset_id, action)` enforces valid `from`-states and appends an event.
Illegal transitions (e.g. deploying an unvalidated asset) are rejected.

## Lineage & reproducibility

- `register_asset` computes `checksum = hash(asset_type, asset_ref, version, lineage)`.
- `record_use` logs each use for decision-level traceability.
- `lineage(asset_id)` returns the full reproducibility bundle: config, version,
  checksum, state and the ordered event trail (register/validate/approve/deploy/
  retire/use with actor + timestamp).

## Relationship to prior phases

This governs the **AI-platform** artifacts. It complements — does not replace —
the Phase 6 ML model registry and the Phase 9 model-governance events, which
continue to govern the ML models themselves.

## Endpoints

`GET /asset-types`, `POST /assets`, `POST /assets/transition`, `GET /assets`,
`GET /summary`, `GET /assets/{id}/lineage`.
RBAC: `aip.governance.view` / `aip.governance.manage`.
