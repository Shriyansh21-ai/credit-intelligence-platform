# Frontend Design System

*The enterprise design language for the AI Credit Intelligence Platform UI.*

The frontend is a React 19 + TypeScript SPA styled with **Tailwind CSS v4** and
**shadcn/ui** (new-york style, Radix primitives). This document is the single
reference for the design tokens and shared primitives that keep every screen
visually consistent. **Always map through these primitives instead of
hand-writing colours** — that is what keeps risk, status and severity semantics
identical across all pages and in both themes.

## Theme & tokens

All colours are defined as CSS variables in [`src/styles.css`](../../frontend/src/styles.css)
and exposed to Tailwind through the `@theme inline` block. The theme is a
**dark-first premium fintech** palette expressed in the perceptual **OKLCH**
colour space. Consume tokens through Tailwind utilities (`bg-card`,
`text-muted-foreground`, `border-border`, …) — never hardcode hex/`slate-700`.

### Semantic surface & intent tokens

| Token | Utility examples | Meaning |
|-------|------------------|---------|
| `background` / `foreground` | `bg-background`, `text-foreground` | Base page surface & text |
| `card` / `card-foreground` | `bg-card` | Elevated surfaces (cards, panels) |
| `muted` / `muted-foreground` | `text-muted-foreground` | Secondary text & subtle fills |
| `primary` / `accent` | `bg-primary`, `text-accent` | Brand & emphasis |
| `success` / `warning` / `info` / `destructive` | `text-success`, `bg-warning/15` | Intent states |
| `border` / `input` / `ring` | `border-border`, `ring-ring` | Lines, fields, focus rings |
| `sidebar-*` | `bg-sidebar` | Navigation shell |

### Risk scale (added in Stage 2 · M1)

A dedicated four-step **risk** scale where **low is good (green)** and
**critical is bad (red)** — semantically distinct from alert *severity* (where a
low-severity item is merely informational).

| Token | Utility | Level |
|-------|---------|-------|
| `risk-low` | `text-risk-low`, `bg-risk-low/15` | Low risk (good) |
| `risk-medium` | `text-risk-medium` | Medium risk |
| `risk-high` | `text-risk-high` | High risk |
| `risk-critical` | `text-risk-critical` | Critical risk (bad) |

Other scales: radius (`--radius` + `rounded-{sm..3xl}`), charts
(`chart-1..5`), gradients (`bg-gradient-primary/-accent/-hero`), and shadows
(`shadow-card`, `shadow-glow`).

## Tone system — `@/lib/status`

[`src/lib/status.ts`](../../frontend/src/lib/status.ts) is the **single source of
truth** for turning domain values into colour classes:

| Helper | Input → output |
|--------|----------------|
| `normalizeRisk(x)` | any value → `"low" \| "medium" \| "high" \| "critical"` |
| `riskBadge / riskText / riskFill(x)` | risk level → badge / text / fill classes |
| `severityTone(sev)` | alert severity → badge classes (critical/high/medium/low) |
| `scoreTone(score)` | credit score → text tone (≥700 good, ≥580 warn, else bad) |
| `gradeTone(grade)` | rating grade (AAA…D) → text tone |
| `statusBadge / statusText(status)` | operational status vocabulary → tone |

`TONE_BADGE`, `TONE_TEXT`, and `TONE_FILL` expose the raw class maps for the nine
semantic `ToneKind`s. The Risk Intelligence `format` module re-exports
`SEVERITY_TONE`, `gradeTone` and `scoreTone` from here, so legacy imports keep
working while the logic lives in one place.

## Shared components

### `@/components/common`

| Component | Purpose |
|-----------|---------|
| `PageHeader` | Standard page heading: title, description, optional icon, right-aligned actions slot; responsive (actions wrap on mobile). |
| `RiskBadge` | Risk-level pill driven by the risk scale; normalises arbitrary input. |
| `StatusBadge` | Operational-status pill; colour derived from the status vocabulary; humanises `snake_case` labels. |

### `@/components/ui` (shadcn/ui)

The full primitive set — `Button`, `Card`, `Table`, `Input`, `Select`,
`Dialog`, `Dropdown`, `Tabs`, `Badge`, `Tooltip`, `Skeleton`, `Sidebar`, etc.
`Badge` gained `success` / `warning` / `info` variants in M1.

### Feature primitives

Cross-feature building blocks are re-exported from feature barrels for reuse:

- `@/features/risk-intelligence` → `MetricCard`, `SectionCard`, `Bar`,
  `SeverityBadge`, `StateWrap` (loading/error/empty gate), `RiskLayout`.
- `@/features/operations` → `OpsLayout` (page shell) + formatters.
- `@/features/ai-platform` re-uses the above for visual consistency.

## Conventions

- **Never** hardcode palette classes (`text-red-500`, `bg-green-600`) for risk,
  status or severity — use the tone helpers or badges above.
- Use semantic intent tokens (`success`/`warning`/`destructive`) for generic
  states; use the `risk-*` scale specifically for credit-risk levels.
- Prefer `PageHeader` for every page's heading block.
- Gate async content through `StateWrap` (loading / error / empty).
- Keep dark mode working: only reference tokens, which resolve per-theme.

---

← Back to [Frontend Documentation](index.md)
