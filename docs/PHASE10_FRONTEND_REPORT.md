# Phase 10 — Frontend Report

**Stack:** TanStack Start + React + React Query + Radix UI + Tailwind (matches Phases 6–9).
**Build:** `npm run build` → **clean** (`✓ built in 8.33s`, exit 0 — TypeScript typechecks
as part of the build). Route tree regenerated with all 12 new routes registered.

## Feature module
`src/features/banking-os/` mirrors the Phase 9 feature convention:
- `api.ts` — typed wrappers over every `/api/os/*` endpoint via the shared `@/lib/http` client.
- `hooks.ts` — React Query `useQuery`/`useMutation` hooks, keyed per module for precise
  cache invalidation.
- `index.ts` — re-exports hooks + the shared `OpsLayout` / `MetricCard` / `SectionCard` /
  `StateWrap` primitives, so Phase 10 pages look identical to the rest of the platform
  (dark/light theme, cards, bars, tone-coded metrics).

## Pages (12 routes, all wired to real APIs — no placeholders)

| Route | Milestone | Highlights |
|-------|-----------|-----------|
| `/executive-center` | M10 | Persona switcher (7 roles), tone-coded KPI cards, chart series |
| `/policy-engine` | M7 | Live rule **playground** (edit rules + input → decision + reasons) |
| `/enterprise-search` | M2 | Search box, mode toggle (keyword/semantic/hybrid), ranked hits with signal breakdown, reindex |
| `/committee-workspace` | M4 | Committees, meetings, decision analytics + approval rate |
| `/scenario-planning` | M5/M6 | Run plan → EL by scenario, Monte Carlo VaR/ES, recommendations |
| `/workflow-studio` | M11 | Definitions + runs with status tones |
| `/recommendation-marketplace` | M12 | Install plugins, run against a PD, priority-ranked recommendations |
| `/data-fabric` | M14 | Catalog, classification breakdown, quality/lineage/contract counts |
| `/graph-analytics` | M1 | UBO lookup, cross-holding cycle detection |
| `/prompt-studio` | M8 | Templates with lifecycle status + deployed version |
| `/llm-console` | M9 | Router tester (strategy → chosen provider + reason), provider registry, cost analytics |
| `/fairness-governance` | M13 | Evaluate cohort → disparate impact / parity, pass-fail verdict, history |

## Navigation
A new **“Banking OS”** section in `src/components/dashboard/Sidebar.tsx` links all 12 pages
with lucide icons, placed after the Autonomous Intelligence section.

## Quality
- Every page gates content with `StateWrap` (loading / error / empty) and reads live data
  through the typed hooks — no mock data.
- Responsive grids (`grid-cols-2 lg:grid-cols-4`), theme-aware tokens (`bg-card`,
  `text-muted-foreground`, tone classes), consistent with the existing design system.
- Production bundle emitted per-route (code-split), e.g. `policy-engine-*.js`,
  `scenario-planning-*.js`, `recommendation-marketplace-*.js`.
