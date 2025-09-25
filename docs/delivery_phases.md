# Delivery Phases Roadmap

This roadmap sequences the program required to transform the existing Ignition Docker tooling into a full DevOps control plane. Each phase builds on hardening performed earlier, ensuring the platform stays aligned with industrial automation best practices while unlocking new capabilities.

## Phase 0 – Container Runtime Hardening
- **Objective**: Stabilise the Docker-based Ignition spin-up workflow so developers receive consistent, production-like gateways with minimal manual intervention.
- **Key Initiatives**:
  - Refine the compose generator to emit long-form mounts for `/data`, modules, JDBC drivers, backups, and secrets while validating host paths ahead of time.
  - Auto-create host directories with secure permissions and detect license or module bundles during render.
  - Layer health checks, deterministic container naming, and configurable resource limits into the templates.
  - Expand automated tests that cover bind mount sanitisation, project root resolution, and secret injection edge cases.
- **Technical Debt Remediation**:
  - Replace ad-hoc path constants with the shared `paths` helper and migrate legacy utilities to the new module.
  - Remove duplicated compose templating logic by centralising helpers in `ComposeConfig` and related services.
  - Document the expected directory structure and environment variable contract for local operators.
- **Dependencies**: Docker Desktop or engine with Compose v2, Ignition image registry access, filesystem permissions on the host.
- **Exit Criteria**:
  - Compose renderings succeed on macOS, Windows (WSL2), and Linux without manual path edits.
  - Persistent `/data` volumes survive container rebuilds and secrets/modules are mounted automatically when present.
  - Automated test suite covering compose generation passes in CI.

## Phase 1 – Web Control Plane MVP
- **Objective**: Deliver the first user-facing SPA and API that orchestrate the hardened Docker workflow while introducing traceable project storage.
- **Key Initiatives**:
  - Build a React/TypeScript single-page app with flows for requesting environments, viewing status, and uploading Ignition assets.
  - Extend the FastAPI layer with CRUD endpoints for environments, project metadata, backups, and secrets placeholders.
  - Integrate Git-backed storage for project archives using content hashing or Git LFS for large binary payloads.
  - Surface baseline monitoring widgets (gateway status, CPU/RAM usage) using the Docker API and gateway REST endpoints.
- **Technical Debt Remediation**:
  - Unify logging, error handling, and configuration loading across the FastAPI services.
  - Establish structured API response schemas and OpenAPI documentation.
  - Stand up CI pipelines for the web client (lint, unit tests, build) and the Python backend (type checks, pytest).
- **Dependencies**: Phase 0 complete, Node.js toolchain, FastAPI deployment target, Git server or local repository storage.
- **Exit Criteria**:
  - Users can provision, list, and tear down Ignition environments entirely through the web app.
  - Project artifacts stored through the app are versioned and traceable with metadata.
  - OpenAPI spec published and validated against integration tests.

## Phase 2 – Automated Delivery Tooling
- **Objective**: Introduce DevOps automation for secrets, deployments, and documentation to reduce manual operations.
- **Key Initiatives**:
  - Integrate Vault or similar secret management, enabling scoped credentials per environment and rotation workflows.
  - Model CI/CD pipelines that promote Ignition projects across dev → staging → production with approvals and automated testing hooks.
  - Expand telemetry ingestion: forward gateway metrics/logs to the platform and expose dashboards and alerts.
  - Automate AI-generated documentation updates triggered by commits or deployments.
- **Technical Debt Remediation**:
  - Refactor environment metadata storage into a persistent relational database with migrations.
  - Abstract pipeline definitions so they can target Docker or Kubernetes runtimes with shared components.
  - Harden RBAC policies across the API and user interface.
- **Dependencies**: Stable Phase 1 release, secrets backend, CI runners, monitoring stack (e.g., Prometheus, Grafana), AI provider access.
- **Exit Criteria**:
  - Pipelines can be configured and executed from the control plane, including promotion gates.
  - Secrets managed centrally with audit logs and automatic injection into running environments.
  - Documentation is regenerated automatically with traceability to source changes.

## Phase 3 – Intelligent Orchestration
- **Objective**: Scale orchestration beyond single-node Docker deployments with predictive operations support.
- **Key Initiatives**:
  - Add Kubernetes support (manifests, Helm charts) and scheduling policies for Ignition clusters.
  - Implement predictive maintenance analytics by correlating telemetry with AI models.
  - Provide guided troubleshooting with AI-powered runbooks and remediation suggestions.
  - Launch a marketplace/catalogue for reusable pipeline and environment templates.
- **Technical Debt Remediation**:
  - Consolidate event streaming with a message bus (NATS/Kafka) for cross-service coordination.
  - Establish canary and rollback strategies for both Docker and Kubernetes environments.
  - Review security posture for multi-cluster, cross-network communication.
- **Dependencies**: Mature Phase 2 services, Kubernetes infrastructure, data science tooling for predictive analytics.
- **Exit Criteria**:
  - Users can choose Docker or Kubernetes targets seamlessly.
  - Predictive alerts reduce unplanned downtime and are validated with historical incident data.
  - Template marketplace supports publishing, discovery, and versioning of automation assets.

## Phase 4 – Enterprise & Ecosystem Expansion
- **Objective**: Support large-scale, multi-tenant programmes and extend the platform to additional automation ecosystems.
- **Key Initiatives**:
  - Implement tenant isolation, billing/chargeback hooks, and delegated administration features.
  - Provide cross-site federation with policy-driven replication of secrets, projects, and telemetry.
  - Offer SDKs and extension points for third parties to integrate non-Ignition runtimes or tooling.
  - Formalise compliance packs (e.g., ISA/IEC 62443, NERC CIP) with automated evidence collection.
- **Technical Debt Remediation**:
  - Optimise service boundaries for scalability (split monolith services where necessary, adopt service mesh if needed).
  - Harden data lifecycle management, including retention policies and GDPR-compliant deletion workflows.
  - Audit and enhance disaster recovery and business continuity procedures.
- **Dependencies**: Established customer base running Phase 3 features, legal/compliance alignment, strategic partners for ecosystem integrations.
- **Exit Criteria**:
  - Multi-tenant customers operate independently with guaranteed isolation and QoS.
  - Federation synchronises projects/secrets across regions with conflict resolution policies.
  - Partner ecosystem contributes certified integrations and extensions.

## Cross-Cutting Practices
- Security reviews, threat modelling, and penetration testing accompany every phase before release.
- Observability (metrics, logging, tracing) is treated as a product feature and enforced across services.
- Documentation remains living: every phase ships updated runbooks, user guides, and architecture diagrams.
- Customer feedback loops (beta groups, design partners) inform backlog grooming before scaling to the next phase.
