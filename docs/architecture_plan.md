# Ignition DevOps Control Plane – Architecture Plan

## 1. Vision and Guiding Principles
- Deliver a unified, browser-based control plane that manages the full SCADA delivery lifecycle (development → testing → staging → production) with an Ignition-first focus.
- Bridge OT and IT expectations by combining infrastructure-as-code discipline, modern DevOps tooling, and industrial automation domain knowledge.
- Provide opinionated defaults that follow Ignition container best practices (persistent data volumes, module and driver overlays) while staying extensible for other SCADA platforms in the future.【6b7505†L1-L67】
- Prioritise security, auditability, and collaboration across distributed engineering teams.

## 2. Primary User Personas
| Persona | Goals | Key Capabilities |
| --- | --- | --- |
| SCADA Developer | Rapidly prototype, test, and promote Ignition projects | On-demand gateway sandboxes, project import/export, tag management |
| System Integrator / Project Lead | Coordinate multiple developers and deployments | Workspace governance, approvals, release orchestration |
| OT/IT Administrator | Maintain secure, compliant infrastructure | Central secrets, access control, monitoring, backups |
| QA / Compliance Analyst | Validate builds and maintain traceability | Automated test suites, change logs, AI-driven documentation |

## 3. Functional Pillars
1. **Environment Orchestration** – Spin up Ignition gateways in Docker/Kubernetes, attach persistent volumes, restore backups, and inject modules/drivers automatically.【6b7505†L1-L67】
2. **Versioned Project Repository** – Git-style workflows adapted for binary Ignition artifacts (e.g., Vision projects, tags) using content-addressable storage and optional LFS.
3. **Secrets & Credentials Hub** – Manage database passwords, OPC UA certificates, activation tokens, and license keys; expose as short-lived runtime secrets.
4. **CI/CD Automation** – Model pipelines that progress artifacts through dev → staging → QA → production with approvals, tests, and change promotion.
5. **Observability & Monitoring** – Aggregate gateway status, metrics, and logs across all environments; expose dashboards, alerts, and auditing.
6. **AI Documentation Assistant** – Continuously summarise project changes, update diagrams, and produce audit-ready narratives using LLM tooling.
7. **Unified Web Interface** – A responsive SPA for managing projects, environments, pipelines, and documentation.

## 4. High-Level Architecture
```
+----------------------+         +-------------------+         +----------------------+
|  Web SPA (React/TS)  | <-----> |  API Gateway      | <-----> |  Microservices Tier  |
|  - Project cockpit   |         |  - AuthN/AuthZ    |         |  - Env Orchestrator  |
|  - Pipelines UI      |         |  - Rate limiting  |         |  - Version Control   |
|  - Docs dashboards   |         |                   |         |  - Secrets Service   |
+----------+-----------+         +---------+---------+         |  - CI/CD Orchestrator|
           |                               |                   |  - Monitoring Proxy  |
           |                               |                   |  - AI Doc Engine     |
           |                               |                   +----------+-----------+
           |                               |                              |
           |                               |                   +----------v-----------+
           |                               |                   |  Data & Messaging    |
           |                               |                   |  - Postgres (config) |
           |                               |                   |  - Object storage    |
           |                               |                   |  - Message bus (NATS)|
           |                               |                   |  - Time-series (TSDB)|
           |                               |                   +----------+-----------+
           |                               |                              |
           |                               |                   +----------v-----------+
           |                               |                   |  Infrastructure Layer|
           |                               |                   |  - Kubernetes / K3s  |
           |                               |                   |  - Docker runtimes   |
           |                               |                   |  - Vault / Secrets   |
           |                               |                   |  - Monitoring stack  |
           |                               |                   +----------------------+
```

## 5. Service Responsibilities
- **API Gateway**: OAuth2/OIDC integration, request authentication, RBAC enforcement, request routing to internal services, rate limiting, audit logging.
- **Environment Orchestrator**:
  - Manage Docker Compose templates, Kubernetes manifests, and Helm charts for Ignition gateways.
  - Handle data volume lifecycle at `/data`, module (`/modules`), JDBC (`/jdbc`), and secret mounts so that backups and third-party packages remain consistent across rebuilds.【6b7505†L1-L67】
  - Provide health monitoring, scaling hooks, and rollback capabilities.
- **Project Repository Service**:
  - Wrap Git with custom diff/merge drivers for Ignition resources (e.g., `.proj`, `.json`, `.xml`).
  - Manage binary assets through object storage buckets and maintain metadata for releases, approvals, and provenance.
- **Secrets Service**:
  - Abstract Vault or cloud secret stores, rotate credentials, manage activation tokens and license keys, and expose templated environment files for runtime containers.
- **CI/CD Orchestrator**:
  - Model multi-stage pipelines, connect to testing frameworks (unit tests, integration simulations), and enforce promotion gates with manual approvals or automated quality metrics.
- **Monitoring & Telemetry Aggregator**:
  - Collect metrics/logs from gateways (via REST, system tags, or log streaming), normalize into time-series storage, and trigger alerts.
- **AI Documentation Engine**:
  - Capture configuration snapshots, Git history, test results, and telemetry, then use LLM prompts to generate/update manuals, diagrams, and compliance reports.
- **Notification & Integration Service**:
  - Send event-driven updates to Slack/Teams, ITSM tools, and ticketing systems; expose webhooks for custom extensions.

## 6. Data Management
- **Relational Store (Postgres)** for metadata: projects, environments, pipeline runs, user permissions, audit trails.
- **Object Storage (S3 compatible)** for large Ignition exports, gateway backups, diagrams, and generated documents.
- **Time-Series Database (TimescaleDB, InfluxDB, or VictoriaMetrics)** for gateway KPIs and performance metrics.
- **Message Bus (NATS/Kafka)** to coordinate pipeline events, environment status updates, and AI processing jobs.

## 7. Deployment and Infrastructure
- Package services as containers orchestrated by Kubernetes (managed cluster or K3s for on-prem OT sites).
- Use Helm charts or Terraform modules to provision infrastructure-as-code per environment.
- Maintain dedicated worker nodes or namespaces for Ignition runtime workloads with access to GPUs/accelerators if AI workloads require them.
- Implement persistent volume claims (PVC) or Docker named volumes for gateway `/data`, mirroring the recommended container pattern for long-lived Ignition state.【6b7505†L1-L26】
- Provide secure ingress via reverse proxies (NGINX/Traefik) and mutual TLS when connecting to on-prem OT networks.

## 8. Security & Compliance
- Centralised identity via SSO (OIDC/SAML) with fine-grained RBAC and scoped API tokens.
- Secrets encrypted at rest and in transit; rotate using Vault policies and provide just-in-time access during pipeline execution.
- Capture immutable audit logs (append-only) for project changes, deployments, secrets access, and AI-generated content provenance.
- Support air-gapped or semi-connected deployments by caching container images and documentation locally.

## 9. Integrations
- **Ignition API Client** for gateway provisioning, tag management, and project publication.
- **Git Providers** (GitHub, GitLab, Bitbucket) for remote mirroring and pull request workflows.
- **Issue Trackers / ITSM** for change management tickets.
- **Monitoring Systems** (Prometheus, Grafana) for sharing dashboards and alerts.
- **AI Platforms** (OpenAI, Azure OpenAI, local LLMs) for documentation engine.

## 10. Sample Lifecycle Flow
1. Developer requests a sandbox → Environment Orchestrator provisions a Docker gateway with persistent `/data`, optional modules, and secrets injected.
2. Developer pushes project changes → Repository Service stores artifacts and triggers CI pipeline.
3. CI orchestrator runs unit/integration tests, publishes preview docs, and requests approval.
4. Upon approval, pipeline promotes the package to staging/production, reusing the same secrets and volume patterns for consistency.
5. Monitoring service updates dashboards and triggers AI engine to refresh manuals and release notes.

## 11. Non-Functional Requirements
- **Scalability**: Horizontal scale via microservices and message queues; orchestrator supports multi-cluster (per site) gateways.
- **Resilience**: Stateful components deployed in HA configurations; automated backups for metadata and object storage; DR playbooks.
- **Extensibility**: Modular service architecture to plug in additional SCADA platforms, connectors, or AI models.
- **Observability**: Structured logging, distributed tracing, and metrics instrumentation for every service.

## 12. Delivery Roadmap
1. **MVP** – Web SPA with environment provisioning (Docker), Git-backed project storage, manual secrets entry, and basic monitoring widgets.
2. **Phase 2** – Automated CI/CD templates, secrets vault integration, telemetry aggregation, and basic AI documentation generation.
3. **Phase 3** – Kubernetes orchestration, advanced analytics (predictive maintenance), AI-assisted troubleshooting, and marketplace for reusable templates.
4. **Phase 4** – Multi-tenant support, cross-site federation, and extensibility for third-party automation platforms beyond Ignition.

## 13. Open Questions
- How will binary Ignition assets be diffed/merged in collaborative scenarios? Investigate custom merge drivers or metadata representations.
- What SLAs/uptime requirements exist for OT sites with intermittent connectivity? Define offline/edge operating modes.
- How should AI-generated documentation be validated and signed off for compliance audits?

## 14. Success Metrics
- Reduced environment provisioning time (< 5 minutes) and automated teardown when idle.
- Adoption of Git-based workflows (number of projects and contributors using the platform).
- Percentage of deployments executed through pipelines versus manual procedures.
- Accuracy and freshness of AI-generated documentation compared to manual baselines.

