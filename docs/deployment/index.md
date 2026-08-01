# Deployment Documentation

*Building, configuring, and shipping the AI Credit Intelligence Platform to production.*

| Document | Description |
| --- | --- |
| [CICD](CICD.md) | Continuous integration and delivery pipelines and gates. |
| [CONFIGURATION](CONFIGURATION.md) | Environment variables, settings, and configuration management. |
| [ENVIRONMENT_PROFILES](ENVIRONMENT_PROFILES.md) | Dev/test/staging/prod profiles, secret management, fail-fast startup validation, and `deploy/env/` templates. |
| [CONTAINERS](CONTAINERS.md) | Container images, Dockerfiles, and runtime packaging. |
| [DEPLOYMENT](DEPLOYMENT.md) | Deployment architecture and release process overview. |
| [DEPLOYMENT_CHECKLIST](DEPLOYMENT_CHECKLIST.md) | Pre-deployment verification checklist. |
| [DEPLOYMENT_GUIDE](DEPLOYMENT_GUIDE.md) | Step-by-step guide for deploying the platform. |
| [GO_LIVE_CHECKLIST](GO_LIVE_CHECKLIST.md) | Final readiness checklist for production go-live. |
| [INFRASTRUCTURE_TERRAFORM](INFRASTRUCTURE_TERRAFORM.md) | Infrastructure-as-code with Terraform. |
| [PRODUCTION_HARDENING](PRODUCTION_HARDENING.md) | Verified production controls: observability/health, security, container/K8s hardening, reliability. |
| [SCALING_GUIDE](SCALING_GUIDE.md) | Horizontal/vertical scaling strategies and capacity planning. |

> [!TIP]
> Deploying for the first time? Follow [DEPLOYMENT_GUIDE](DEPLOYMENT_GUIDE.md), then work
> through the [DEPLOYMENT_CHECKLIST](DEPLOYMENT_CHECKLIST.md) and
> [GO_LIVE_CHECKLIST](GO_LIVE_CHECKLIST.md).

← Back to [Documentation Home](../index.md)
