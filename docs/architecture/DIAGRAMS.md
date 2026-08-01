# Architecture Diagrams

A visual reference for the AI Credit Intelligence Platform. Every diagram below
renders natively on GitHub (Mermaid). They are grouped into **System**,
**Frontend**, **Backend & Data**, **AI / ML pipelines**, **Security**, and
**Deployment**.

> These diagrams are documentation of the shipped system — the FastAPI backend
> under `backend/app`, the TanStack Start frontend under `frontend/src`, the
> Alembic-managed relational store, and the container/Kubernetes deployment
> assets under `deploy/` and `infra/`.

---

## 1. Overall System Architecture

```mermaid
flowchart TB
  subgraph Client["Client Tier"]
    Browser["Web App · TanStack Start + React 19"]
    APIClients["API Consumers · Open API / SDK"]
  end

  subgraph Edge["Edge Tier"]
    CDN["CDN / Static Assets"]
    LB["Load Balancer + TLS Termination"]
    WAF["WAF · Rate Limiting · Security Headers"]
  end

  subgraph App["Application Tier — FastAPI"]
    API["REST API · /api/*"]
    MW["Middleware · Auth · RBAC · Audit · Tenant"]
    Domains["Domain Modules · Credit · Risk · ML · Banking OS · SaaS · AI"]
  end

  subgraph Intel["Intelligence Tier"]
    ML["ML Serving · Scoring · Fraud · Drift"]
    AI["AI Platform · RAG · Agents · Copilot"]
    OCR["Document AI · OCR / Extraction"]
  end

  subgraph Data["Data Tier"]
    RDB[("Relational DB · SQLAlchemy + Alembic")]
    Cache[("Cache · Sessions / Hot Reads")]
    Store[("Object Storage · Documents / Models")]
    Vector[("Vector Index · Embeddings")]
  end

  subgraph Ext["External Ecosystem"]
    Bureau["Credit Bureaus"]
    GST["GST / MCA Registries"]
    AA["Account Aggregator"]
    LLM["LLM Providers"]
  end

  Browser --> CDN
  Browser --> LB
  APIClients --> LB
  LB --> WAF --> API
  API --> MW --> Domains
  Domains --> ML & AI & OCR
  Domains --> RDB & Cache & Store
  AI --> Vector & LLM
  Domains --> Bureau & GST & AA
```

---

## 2. Frontend Architecture

```mermaid
flowchart TB
  subgraph Shell["App Shell"]
    Root["__root · providers, theme, error boundary"]
    Router["TanStack Router · 100+ file routes"]
    Palette["Global Command Palette (⌘K)"]
  end

  subgraph Features["Feature Modules (src/features/*)"]
    F1["risk-intelligence"]
    F2["financial-intelligence"]
    F3["ml-platform"]
    F4["ai-platform"]
    F5["banking-os"]
    F6["operations · dashboards"]
    F7["…14 domains total"]
  end

  subgraph Shared["Shared Layer"]
    UI["ui/ · shadcn + Radix primitives"]
    Common["common/ · PageHeader · EmptyState · ErrorState · Skeletons"]
    Charts["Recharts wrappers · chart-theme"]
    Http["lib/http · apiGet/Post + demo interception"]
    Query["TanStack Query · cache + retries"]
  end

  Root --> Router --> Features
  Router --> Palette
  Features --> Shared
  Features --> Http --> Query
  Shared --> UI & Common & Charts
```

Each route is a thin wrapper that composes primitives from its feature module —
keeping pages consistent and the design system single-sourced.

---

## 3. Backend Architecture (Clean Architecture / DDD)

```mermaid
flowchart TB
  subgraph Interface["Interface Layer"]
    Routers["FastAPI Routers · /api/*"]
    Schemas["Pydantic Schemas · request/response"]
  end
  subgraph AppLayer["Application Layer"]
    Services["Domain Services · use cases"]
    Policies["Policy / RBAC Enforcement"]
  end
  subgraph DomainLayer["Domain Layer"]
    Models["Domain Models · entities"]
    Rules["Business Rules · scoring, covenants, limits"]
  end
  subgraph Infra["Infrastructure Layer"]
    ORM["SQLAlchemy ORM"]
    Repos["Repositories"]
    Integrations["Connectors · bureau / GST / AA / ERP"]
    MLAdapters["ML / LLM Adapters"]
  end

  Routers --> Schemas --> Services
  Services --> Policies
  Services --> Rules --> Models
  Services --> Repos --> ORM
  Services --> Integrations & MLAdapters
```

---

## 4. Database Architecture

```mermaid
erDiagram
  USER ||--o{ APPLICATION : "submits/owns"
  USER }o--o{ ROLE : "assigned"
  ROLE }o--o{ PERMISSION : "grants"
  APPLICATION ||--o{ FINANCIAL_STATEMENT : "has"
  APPLICATION ||--o{ DOCUMENT : "attaches"
  APPLICATION ||--o{ PREDICTION : "scored_by"
  APPLICATION ||--o{ COVENANT : "monitored_by"
  APPLICATION ||--o{ MONITORING_ALERT : "raises"
  APPLICATION ||--o{ APPROVAL : "routed_through"
  APPLICATION ||--o{ COMMITTEE_DECISION : "decided_in"
  PREDICTION ||--o{ EXPLANATION : "explained_by"
  MODEL_REGISTRY ||--o{ PREDICTION : "serves"
  TENANT ||--o{ USER : "scopes"
  TENANT ||--o{ APPLICATION : "isolates"
  AUDIT_EVENT }o--|| USER : "actor"
```

The store is managed exclusively through **Alembic migrations** — the physical
schema is never hand-edited. Multi-tenant tables carry a `tenant_id` scope
enforced at the query layer.

---

## 5. Enterprise Banking Workflow (Credit Decision Lifecycle)

```mermaid
flowchart LR
  Intake["Application Intake"] --> KYC["KYC / KYB + Bureau Pull"]
  KYC --> Docs["Document Ingestion + OCR"]
  Docs --> Spread["Financial Spreading"]
  Spread --> Score["AI Credit Scoring"]
  Score --> Fraud["Fraud / AML Screening"]
  Fraud --> Risk["Risk Rating + Limits"]
  Risk --> Decision{"Auto-Decision?"}
  Decision -- "Within policy" --> AutoApprove["Auto-Approve"]
  Decision -- "Referral" --> Committee["Credit Committee"]
  Committee --> Approve["Approve / Reject / Condition"]
  AutoApprove --> Disburse["Sanction + Disbursal"]
  Approve --> Disburse
  Disburse --> Monitor["Portfolio Monitoring"]
  Monitor --> EWS["Early-Warning Signals"]
  EWS -->|breach| Review["Covenant Review / Remediation"]
  Review --> Monitor
```

---

## 6. AI Pipeline

```mermaid
flowchart LR
  Input["Structured + Unstructured Inputs"] --> FE["Feature Engineering"]
  FE --> Ensemble["Scoring Ensemble"]
  Ensemble --> XAI["Explainability · SHAP / reason codes"]
  XAI --> Narrative["LLM Narrative Generation"]
  Narrative --> Guard["Guardrails · PII · policy · hallucination checks"]
  Guard --> Output["Analyst-facing Decision + Rationale"]
  Output --> Feedback["Human Feedback"]
  Feedback --> Learning["Continuous Learning Loop"]
  Learning --> FE
```

---

## 7. ML Pipeline (MLOps Lifecycle)

```mermaid
flowchart TB
  Data["Curated Datasets"] --> Train["Training + Validation"]
  Train --> Eval["Evaluation · AUC · KS · fairness"]
  Eval --> Registry["Model Registry · versioned"]
  Registry --> Approve{"Governance Sign-off"}
  Approve -- approved --> Deploy["Serving Deployment"]
  Approve -- rejected --> Train
  Deploy --> Serve["Real-time Inference"]
  Serve --> Monitor["Monitoring · drift · PSI · latency"]
  Monitor -->|drift detected| Retrain["Retraining Trigger"]
  Retrain --> Train
```

---

## 8. OCR / Document Processing Pipeline

```mermaid
flowchart LR
  Upload["Upload · PDF / image / scan"] --> Classify["Document Classification"]
  Classify --> Preprocess["Preprocess · deskew · denoise"]
  Preprocess --> OCR["OCR · text + layout"]
  OCR --> Extract["Field Extraction · KV + tables"]
  Extract --> Validate["Validation · schema + cross-checks"]
  Validate --> Reconcile["Reconciliation vs declared figures"]
  Reconcile --> Persist["Persist · structured financials"]
  Persist --> Index["Index for Retrieval"]
```

---

## 9. RAG Pipeline

```mermaid
flowchart LR
  Docs["Source Corpus · filings · policy · memos"] --> Chunk["Chunking"]
  Chunk --> Embed["Embedding"]
  Embed --> VStore[("Vector Index")]
  Query["User / Agent Query"] --> QEmbed["Query Embedding"]
  QEmbed --> Retrieve["Hybrid Retrieval · vector + keyword"]
  VStore --> Retrieve
  Retrieve --> Rerank["Re-ranking"]
  Rerank --> Context["Context Assembly"]
  Context --> LLM["LLM Generation"]
  LLM --> Cite["Grounded Answer + Citations"]
```

---

## 10. Agent Architecture

```mermaid
flowchart TB
  Goal["Goal / Task"] --> Planner["Planner"]
  Planner --> Loop{"Reason–Act Loop"}
  Loop --> Tools["Tool Use · retrieval · calculators · APIs"]
  Tools --> Obs["Observation"]
  Obs --> Loop
  Loop --> Memory["Memory · short + long term"]
  Memory --> Loop
  Loop --> Guard["Governance · policy · budget · approval gates"]
  Guard --> Result["Result + Audit Trail"]
```

---

## 11. Security Architecture (Defense in Depth)

```mermaid
flowchart TB
  subgraph Perimeter
    TLS["TLS / HTTPS"] --> WAF["WAF · rate limit · headers"]
  end
  subgraph Identity
    AuthN["Authentication · JWT"] --> AuthZ["Authorization · RBAC"]
    AuthZ --> Tenant["Tenant Isolation"]
  end
  subgraph AppSec
    Validate["Input Validation · Pydantic"] --> Secrets["Secret Management"]
    Secrets --> Audit["Immutable Audit Log"]
  end
  subgraph DataSec
    Encrypt["Encryption at Rest + in Transit"] --> PII["PII Protection / Masking"]
    PII --> Retention["Retention + Privacy Controls"]
  end
  WAF --> AuthN
  Tenant --> Validate
  Audit --> Encrypt
```

---

## 12. Authentication Flow

```mermaid
sequenceDiagram
  actor U as User
  participant FE as Frontend
  participant API as Auth API
  participant DB as User Store
  U->>FE: Enter credentials
  FE->>API: POST /login
  API->>DB: Verify credentials (hashed)
  DB-->>API: User + roles
  API-->>FE: Signed JWT (+ expiry)
  FE->>FE: Store token
  FE->>API: Request + Bearer token
  API-->>FE: 401 → redirect to /login (on expiry)
```

---

## 13. Authorization Flow (RBAC)

```mermaid
flowchart LR
  Req["Authenticated Request"] --> Resolve["Resolve User → Roles"]
  Resolve --> Perms["Expand Roles → Permissions"]
  Perms --> Check{"Has required permission?"}
  Check -- yes --> Scope{"Tenant / row scope ok?"}
  Check -- no --> Deny["403 + audit(denied)"]
  Scope -- yes --> Allow["Execute + audit(success)"]
  Scope -- no --> Deny
```

---

## 14. Deployment Architecture

```mermaid
flowchart TB
  subgraph CICD["CI/CD"]
    Git["Git Push / PR"] --> Pipeline["Lint · Typecheck · Test · Build"]
    Pipeline --> Images["Container Images"]
    Images --> Scan["Image + Dependency Scan"]
  end
  subgraph Runtime["Runtime"]
    Registry["Container Registry"] --> Orchestrator["Kubernetes"]
    Orchestrator --> FEPods["Frontend Pods"]
    Orchestrator --> APIPods["API Pods (HPA)"]
    Orchestrator --> Workers["Async Workers"]
  end
  Scan --> Registry
  APIPods --> DB[("Managed DB")]
  APIPods --> Cache[("Cache")]
  APIPods --> Store[("Object Storage")]
```

---

## 15. Kubernetes Architecture

```mermaid
flowchart TB
  Ingress["Ingress + TLS"] --> SvcFE["Service · frontend"]
  Ingress --> SvcAPI["Service · api"]
  SvcFE --> DFE["Deployment · frontend (ReplicaSet)"]
  SvcAPI --> DAPI["Deployment · api + HPA"]
  DAPI --> CM["ConfigMap · non-secret config"]
  DAPI --> Sec["Secret · credentials"]
  DAPI --> PVC["PersistentVolume · storage"]
  subgraph Observability
    Probes["Liveness / Readiness Probes"]
    Metrics["Metrics + Tracing Sidecars"]
  end
  DAPI --> Probes & Metrics
```

---

## 16. Microservice / Module Interaction

```mermaid
flowchart LR
  Gateway["API Gateway"] --> Credit["Credit"]
  Gateway --> Risk["Risk Intelligence"]
  Gateway --> ML["ML Platform"]
  Gateway --> AI["AI Platform"]
  Gateway --> Bank["Banking OS"]
  Gateway --> SaaS["SaaS Platform"]
  Credit --> ML
  Risk --> ML
  AI --> Risk
  Bank --> Credit
  SaaS -. cross-cutting: tenancy, billing, flags .-> Credit & Risk & ML & AI & Bank
```

---

## 17. Multi-Tenant Architecture

```mermaid
flowchart TB
  Req["Request + JWT"] --> Extract["Extract tenant_id"]
  Extract --> Ctx["Tenant Context (request-scoped)"]
  Ctx --> Filter["Row-level Scoping (tenant_id)"]
  Filter --> Shared[("Shared Schema · pooled")]
  Ctx --> Flags["Per-Tenant Feature Flags"]
  Ctx --> Billing["Per-Tenant Usage Metering"]
  Ctx --> Limits["Per-Tenant Rate Limits"]
```

---

## 18. Banking Ecosystem Integration

```mermaid
flowchart TB
  Platform["Platform Core"] --> Conn["Connector Framework"]
  Conn --> GST["GST / MCA"]
  Conn --> Bureau["Credit Bureaus"]
  Conn --> AA["Account Aggregator"]
  Conn --> ERP["ERP / Accounting"]
  Conn --> Pay["Payments"]
  Conn --> Coll["Collateral Registries"]
  Conn --> C360["Customer 360"]
  Conn --> Sync["Sync Engine · scheduling + reconciliation"]
  Conn --> OpenAPI["Open API · partner access"]
```

---

## 19. Knowledge Graph

```mermaid
flowchart LR
  Borrower(("Borrower")) --- Group(("Corporate Group"))
  Borrower --- Director(("Director"))
  Director --- OtherCo(("Related Entity"))
  Borrower --- Collateral(("Collateral"))
  Borrower --- Exposure(("Exposure"))
  Group --- Sector(("Sector"))
  Borrower --- Events(("Risk Events"))
  Events --- EWS(("Early-Warning Signal"))
```

Relationship traversal surfaces hidden concentration, related-party exposure and
contagion paths that flat tables cannot express.

---

## 20. Digital Twin

```mermaid
flowchart TB
  Real["Live Portfolio State"] --> Twin["Digital Twin Model"]
  Scenario["Scenario Inputs · rates · FX · macro shock"] --> Twin
  Twin --> Simulate["Simulation Engine"]
  Simulate --> Impact["Projected Impact · PD / LGD / capital"]
  Impact --> Compare{"vs Thresholds"}
  Compare -- breach --> Actions["Recommended Actions"]
  Compare -- ok --> Report["Scenario Report"]
```

---

## 21. Workflow Engine

```mermaid
stateDiagram-v2
  [*] --> Draft
  Draft --> Submitted: submit
  Submitted --> UnderReview: assign
  UnderReview --> PendingApproval: recommend
  PendingApproval --> Committee: refer
  PendingApproval --> Approved: approve
  Committee --> Approved: approve
  Committee --> Rejected: reject
  UnderReview --> Rejected: reject
  Approved --> Disbursed: disburse
  Disbursed --> Monitoring: activate
  Monitoring --> [*]
  Rejected --> [*]
```

---

## 22. Request Lifecycle (Middleware Stack)

```mermaid
sequenceDiagram
  participant C as Client
  participant MW as Middleware Stack
  participant R as Router
  participant S as Service
  participant D as Data
  C->>MW: HTTP request
  MW->>MW: Security headers · CORS
  MW->>MW: Rate limit
  MW->>MW: Authenticate (JWT)
  MW->>MW: Resolve tenant + RBAC
  MW->>R: Dispatch
  R->>S: Validated command
  S->>D: Read / write
  D-->>S: Result
  S-->>R: Response model
  R-->>MW: Serialize
  MW->>MW: Audit event
  MW-->>C: Response
```

---

_See also: [`ARCHITECTURE.md`](./ARCHITECTURE.md) (narrative + ADRs),
[`SYSTEM_ARCHITECTURE_FINAL.md`](./SYSTEM_ARCHITECTURE_FINAL.md),
[`DATABASE_ARCHITECTURE_FINAL.md`](./DATABASE_ARCHITECTURE_FINAL.md), and the
domain deep-dives under [`../ai/`](../ai/) and [`../security/`](../security/)._
