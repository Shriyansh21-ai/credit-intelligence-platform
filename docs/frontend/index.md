# Frontend Documentation

*The React single-page application for the AI Credit Intelligence Platform.*

The frontend is a **React 19 + TypeScript 5.8** SPA built with **Vite 7**, located under
`frontend/src`. Routing is file-based, and the UI is organized around self-contained feature
modules.

## Application layout

| Area | Location | Responsibility |
| --- | --- | --- |
| Routes | `frontend/src/routes/` | **102 file-based routes** powered by TanStack Router. |
| Features | `frontend/src/features/` | Domain feature modules (see below). |
| Components | `frontend/src/components/` | Shared, reusable UI components. |
| Hooks | `frontend/src/hooks/` | Reusable React hooks. |
| Lib | `frontend/src/lib/` | Client utilities, API clients, and helpers. |
| Server | `frontend/src/server/` | Server-side / data-layer integration code. |

## Feature modules

`ai-platform`, `autonomous-intelligence`, `banking-os`, `documents`,
`enterprise-assessment`, `enterprise-platform`, `financial-analysis`,
`financial-intelligence`, `integrations`, `ml-platform`, `operations`,
`risk-intelligence`.

## Design system

| Document | Description |
| --- | --- |
| [DESIGN_SYSTEM](DESIGN_SYSTEM.md) | The enterprise design language — theme tokens, the risk/status tone system (`@/lib/status`), and shared primitives (`PageHeader`, `RiskBadge`, `StatusBadge`, shadcn/ui). |

## Core libraries

- **TanStack Query** — server-state management and data fetching.
- **Tailwind CSS v4** — utility-first styling with an OKLCH, token-driven theme.
- **shadcn/ui + Radix** — accessible component primitives.
- **Recharts** — data visualization and charting.
- **Framer Motion** — animation and transitions.

> [!TIP]
> The frontend consumes the backend `/api/*` surface documented in the
> [API documentation](../api/index.md).

← Back to [Documentation Home](../index.md)
