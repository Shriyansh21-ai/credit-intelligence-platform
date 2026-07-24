"""Multi-Tenant Enterprise SaaS Platform (Phase 8).

A fully additive cloud-native platform layer over the Phases 1-7 credit system.
Sub-modules, one per milestone group:

    context / repository      M1  tenant isolation primitives
    tenancy                   M1/M2 org hierarchy, membership, invitations
    branding                  M3  white-label theming + custom domains
    billing/                  M4  subscriptions, metering, invoices
    flags/                    M5  feature flags + rollout
    jobs                      M6  background job platform
    storage                   M7  cloud storage abstraction
    realtime                  M8  websockets / activity stream / presence
    observability             M9  tracing, metrics, health
    cache                     M10 tenant-aware cache platform
    admin                     M12 super-admin console
    analytics                 M13 SaaS analytics
    security                  M14 secrets, sessions, IdP, rate limiting
    seeding                   startup bootstrap (plans/flags/default tenant)
"""

from backend.app.services.saas import (  # noqa: F401
    admin, analytics, branding, cache, context, jobs, observability,
    realtime, repository, security, seeding, storage, tenancy,
)
